package com.driveworkspace.uploader.internal

import com.driveworkspace.uploader.api.DriveUploaderConfig
import com.driveworkspace.uploader.api.UploadError
import com.driveworkspace.uploader.api.UploadSession
import com.driveworkspace.uploader.internal.checkpoint.LocalCheckpointStore
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files
import java.time.Instant
import kotlin.random.Random
import kotlin.time.Duration.Companion.milliseconds

class ResumableUploadEngineTest {

    private lateinit var server: MockWebServer
    private lateinit var tempFile: File
    private lateinit var dao: FakeCheckpointDao
    private lateinit var store: LocalCheckpointStore
    private lateinit var engine: ResumableUploadEngine

    private val totalBytes = 256 * 1024 * 3 + 1234 // 768 KiB + 1234 → 4 chunks at 256KiB
    private val chunkSize = 256 * 1024
    private val mimeType = "application/octet-stream"

    private val config = DriveUploaderConfig(
        chunkSizeBytes = chunkSize,
        maxAttemptsPerChunk = 4,
        maxSessionInitiations = 3,
        initialBackoff = 1.milliseconds,
        maxBackoff = 4.milliseconds,
        backoffJitter = 0.0,
    )

    @Before fun setUp() {
        server = MockWebServer().apply { start() }
        tempFile = Files.createTempFile("upload", ".bin").toFile().apply {
            writeBytes(Random(7).nextBytes(totalBytes))
        }
        dao = FakeCheckpointDao()
        store = LocalCheckpointStore(dao, nowMs = { 1L })
        engine = ResumableUploadEngine(
            httpClient = OkHttpClient(),
            checkpointStore = store,
            retryPolicy = RetryPolicy(config, Random(0)),
            config = config,
        )
    }

    @After fun tearDown() {
        server.shutdown()
        tempFile.delete()
    }

    private fun session(): UploadSession = UploadSession(
        uploadUrl = server.url("/upload-session/abc").toString(),
        remoteFileId = "drive-123",
        expiresAt = Instant.now().plusSeconds(600),
    )

    private fun resumeIncomplete(uptoIncl: Long) = MockResponse()
        .setResponseCode(308)
        .addHeader("Range", "bytes=0-$uptoIncl")

    private fun success(webViewLink: String? = "https://drive.google.com/file/d/X/view") =
        MockResponse()
            .setResponseCode(200)
            .setBody("""{"id":"drive-123","webViewLink":"$webViewLink"}""")

    @Test fun `happy path uploads all chunks and returns success`() = runTest {
        // Three intermediate 308s and a final 200 (total = 3 full chunks + 1 partial = 4 PUTs)
        server.enqueue(resumeIncomplete(chunkSize - 1L))
        server.enqueue(resumeIncomplete(2L * chunkSize - 1))
        server.enqueue(resumeIncomplete(3L * chunkSize - 1))
        server.enqueue(success())

        var lastProgress = 0L to 0L
        val outcome = engine.upload(tempFile, session(), mimeType) { u, t -> lastProgress = u to t }

        assertTrue(outcome is ResumableUploadEngine.Outcome.Success)
        assertEquals(totalBytes.toLong() to totalBytes.toLong(), lastProgress)
        assertEquals(4, server.requestCount)
        assertEquals(null, dao.findByPath(tempFile.absolutePath))
    }

    @Test fun `5xx retries the chunk then succeeds`() = runTest {
        server.enqueue(MockResponse().setResponseCode(503))
        server.enqueue(resumeIncomplete(chunkSize - 1L))
        server.enqueue(resumeIncomplete(2L * chunkSize - 1))
        server.enqueue(resumeIncomplete(3L * chunkSize - 1))
        server.enqueue(success())

        val outcome = engine.upload(tempFile, session(), mimeType) { _, _ -> }
        assertTrue(outcome is ResumableUploadEngine.Outcome.Success)
        assertEquals(5, server.requestCount)
    }

    @Test fun `429 retries and eventually succeeds`() = runTest {
        server.enqueue(MockResponse().setResponseCode(429).addHeader("Retry-After", "0"))
        server.enqueue(resumeIncomplete(chunkSize - 1L))
        server.enqueue(resumeIncomplete(2L * chunkSize - 1))
        server.enqueue(resumeIncomplete(3L * chunkSize - 1))
        server.enqueue(success())

        val outcome = engine.upload(tempFile, session(), mimeType) { _, _ -> }
        assertTrue(outcome is ResumableUploadEngine.Outcome.Success)
    }

    @Test fun `410 returns SessionExpired`() = runTest {
        server.enqueue(MockResponse().setResponseCode(410))
        val outcome = engine.upload(tempFile, session(), mimeType) { _, _ -> }
        assertEquals(ResumableUploadEngine.Outcome.SessionExpired, outcome)
    }

    @Test fun `4xx is non-retryable and fails immediately`() = runTest {
        server.enqueue(MockResponse().setResponseCode(403).setBody("forbidden"))
        val outcome = engine.upload(tempFile, session(), mimeType) { _, _ -> }
        assertTrue(outcome is ResumableUploadEngine.Outcome.Failed)
        val err = (outcome as ResumableUploadEngine.Outcome.Failed).error
        assertTrue(err is UploadError.Http4xx)
        assertEquals(403, (err as UploadError.Http4xx).code)
    }

    @Test fun `connection drop retries the chunk`() = runTest {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AT_START))
        server.enqueue(resumeIncomplete(chunkSize - 1L))
        server.enqueue(resumeIncomplete(2L * chunkSize - 1))
        server.enqueue(resumeIncomplete(3L * chunkSize - 1))
        server.enqueue(success())

        val outcome = engine.upload(tempFile, session(), mimeType) { _, _ -> }
        assertTrue(outcome is ResumableUploadEngine.Outcome.Success)
    }

    @Test fun `running 5xx exhausts the retry budget`() = runTest {
        repeat(config.maxAttemptsPerChunk) { server.enqueue(MockResponse().setResponseCode(500)) }
        val outcome = engine.upload(tempFile, session(), mimeType) { _, _ -> }
        assertTrue(outcome is ResumableUploadEngine.Outcome.Failed)
        assertTrue((outcome as ResumableUploadEngine.Outcome.Failed).error is UploadError.Http5xx)
    }

    @Test fun `resume from existing checkpoint uses queryServerOffset`() = runTest {
        // Pre-seed checkpoint at half the file
        val sess = session()
        val resumePoint = 2L * chunkSize
        store.begin(tempFile.absolutePath, sess.uploadUrl, sess.remoteFileId, totalBytes.toLong())
        store.advance(tempFile.absolutePath, resumePoint)

        // First request will be the offset query (PUT */total) — server says it has 2*chunkSize-1
        server.enqueue(resumeIncomplete(2L * chunkSize - 1))
        // Then 1 more chunk + final
        server.enqueue(resumeIncomplete(3L * chunkSize - 1))
        server.enqueue(success())

        val outcome = engine.upload(tempFile, sess, mimeType) { _, _ -> }
        assertTrue(outcome is ResumableUploadEngine.Outcome.Success)
        // Validate the offset query was a "*" range
        val first = server.takeRequest()
        assertEquals("bytes */$totalBytes", first.getHeader("Content-Range"))
    }

    @Test fun `missing file fails fast`() = runTest {
        tempFile.delete()
        val outcome = engine.upload(tempFile, session(), mimeType) { _, _ -> }
        assertTrue(outcome is ResumableUploadEngine.Outcome.Failed)
        assertTrue((outcome as ResumableUploadEngine.Outcome.Failed).error is UploadError.FileMissing)
    }
}
