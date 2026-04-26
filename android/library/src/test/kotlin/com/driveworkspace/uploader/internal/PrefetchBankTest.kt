package com.driveworkspace.uploader.internal

import com.driveworkspace.uploader.api.DriveUploaderConfig
import com.driveworkspace.uploader.api.UploadInitiator
import com.driveworkspace.uploader.api.UploadProgress
import com.driveworkspace.uploader.api.UploadRequest
import com.driveworkspace.uploader.api.UploadSession
import com.driveworkspace.uploader.internal.checkpoint.BankStore
import com.driveworkspace.uploader.internal.checkpoint.LocalCheckpointStore
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files
import java.time.Instant
import java.util.concurrent.atomic.AtomicInteger
import kotlin.random.Random
import kotlin.time.Duration.Companion.days
import kotlin.time.Duration.Companion.milliseconds

/**
 * Behavioural tests for the ADR-0003 session prefetch bank.
 *
 * These exercise [BankStore] directly and via [DriveUploaderImpl] using
 * the in-memory [FakeBankedSessionDao] so the suite stays JVM-only (no
 * Robolectric, no Room runtime).
 */
class PrefetchBankTest {

    private val config = DriveUploaderConfig(
        chunkSizeBytes = 256 * 1024,
        maxAttemptsPerChunk = 1,
        maxSessionInitiations = 1,
        initialBackoff = 1.milliseconds,
        maxBackoff = 1.milliseconds,
    )

    @Test
    fun `prefetch banks N sessions and a draw shrinks the bank to N-1`() = runTest {
        val dao = FakeBankedSessionDao()
        val bank = BankStore(dao)
        val template = req(mime = "image/jpeg", kind = "photo", size = 500_000)
        val sessions = (1..5).map { fakeSession("url-$it", "rid-$it") }

        val banked = bank.bank(template, sessions)
        assertEquals(5, banked)
        assertEquals(5, bank.count())

        val drawn = bank.tryDraw(template)
        assertNotNull(drawn)
        assertEquals(4, bank.count())
    }

    @Test
    fun `concurrent draws never return the same row`() = runBlocking {
        val dao = FakeBankedSessionDao()
        val bank = BankStore(dao)
        val template = req(mime = "image/jpeg", kind = "photo", size = 500_000)
        val poolSize = 20
        bank.bank(template, (1..poolSize).map { fakeSession("url-$it", "rid-$it") })

        // Fire 4×poolSize concurrent draws against a pool of poolSize. Each
        // draw must return either a unique row or null; never a duplicate.
        coroutineScope {
            val claims = (1..poolSize * 4).map {
                async { bank.tryDraw(template) }
            }.awaitAll()

            val nonNull = claims.filterNotNull()
            assertEquals(
                "expected exactly $poolSize successful draws against a pool of $poolSize",
                poolSize, nonNull.size,
            )
            val urls = nonNull.map { it.uploadUrl }.toSet()
            assertEquals(
                "draws returned duplicate urls: ${nonNull.map { it.uploadUrl }}",
                poolSize, urls.size,
            )
        }
        assertEquals(0, bank.count())
    }

    @Test
    fun `stale sessions are pruned on bank-touch`() = runTest {
        var nowMs = 0L
        val dao = FakeBankedSessionDao()
        val bank = BankStore(
            dao = dao,
            nowMs = { nowMs },
            staleAfter = 5.days,
        )
        val template = req(mime = "image/jpeg", kind = "photo", size = 500_000)

        nowMs = 0L
        bank.bank(template, listOf(fakeSession("old", "rid-old")))
        assertEquals(1, bank.count())

        // Advance past the 5-day TTL — the next bank-touch prunes.
        nowMs = 6.days.inWholeMilliseconds

        val drawn = bank.tryDraw(template)
        assertNull("stale row should not be drawable", drawn)
        assertEquals("stale row should have been pruned", 0, bank.count())
    }

    @Test
    fun `bank miss falls through to live initiate`() = runTest {
        val dao = FakeBankedSessionDao()
        val bank = BankStore(dao)
        val initiateCalls = AtomicInteger(0)
        val initiator = UploadInitiator { _, count ->
            initiateCalls.incrementAndGet()
            List(count) { fakeSession("live-${initiateCalls.get()}-$it", "rid-live") }
        }

        val tempFile = Files.createTempFile("prefetch-miss", ".bin").toFile()
        tempFile.writeBytes(Random.Default.nextBytes(16))
        tempFile.deleteOnExit()

        val impl = newImpl(initiator, bank)

        val emissions = impl.upload(tempFile, req()).toList()

        assertEquals(
            "bank was empty; initiator should be called exactly once for the upload",
            1, initiateCalls.get(),
        )
        // The fake live URL won't actually 200, so we expect a Failed
        // emission downstream — but the assertion that matters is that
        // initiate was invoked.
        assertTrue(
            "expected at least one Initiating emission, got: $emissions",
            emissions.any { it is UploadProgress.Initiating },
        )
        cleanup(tempFile)
    }

    @Test
    fun `banked session matches and initiator is not called`() = runTest {
        val dao = FakeBankedSessionDao()
        val bank = BankStore(dao)
        val template = req(mime = "image/jpeg", kind = "photo", size = 500_000)
        bank.bank(template, listOf(fakeSession("banked", "rid-banked")))

        val initiateCalls = AtomicInteger(0)
        val initiator = UploadInitiator { _, count ->
            initiateCalls.incrementAndGet()
            List(count) { fakeSession("should-not-be-used", "rid-x") }
        }

        val tempFile = Files.createTempFile("prefetch-hit", ".bin").toFile()
        tempFile.writeBytes(Random.Default.nextBytes(16))
        tempFile.deleteOnExit()

        val impl = newImpl(initiator, bank)
        impl.upload(tempFile, template).toList()

        assertEquals(
            "bank had a matching session; initiator must not be called",
            0, initiateCalls.get(),
        )
        assertEquals("banked session was drawn", 0, bank.count())
        cleanup(tempFile)
    }

    @Test
    fun `sessions matching different fingerprints don't collide`() = runTest {
        val dao = FakeBankedSessionDao()
        val bank = BankStore(dao)

        val photoSmall = req(mime = "image/jpeg", kind = "photo", size = 500_000)
        val photoLarge = req(mime = "image/jpeg", kind = "photo", size = 30_000_000) // 10–50MB bracket
        val audioSmall = req(mime = "audio/mp4", kind = "audio", size = 500_000)

        bank.bank(photoSmall, listOf(fakeSession("ps-1", "rid-ps-1")))
        bank.bank(photoLarge, listOf(fakeSession("pl-1", "rid-pl-1")))
        bank.bank(audioSmall, listOf(fakeSession("as-1", "rid-as-1")))
        assertEquals(3, bank.count())

        val drawnPhoto = bank.tryDraw(photoSmall)
        assertEquals("https://stub.invalid/ps-1", drawnPhoto?.uploadUrl)
        assertNull(
            "drawing photoSmall again must not return the audioSmall row",
            bank.tryDraw(photoSmall),
        )
        assertEquals(2, bank.count())

        val drawnAudio = bank.tryDraw(audioSmall)
        assertEquals("https://stub.invalid/as-1", drawnAudio?.uploadUrl)

        val drawnLarge = bank.tryDraw(photoLarge)
        assertEquals("https://stub.invalid/pl-1", drawnLarge?.uploadUrl)
        assertEquals(0, bank.count())
    }

    @Test
    fun `prefetchSessions caps at MAX_PREFETCH_COUNT`() = runTest {
        val dao = FakeBankedSessionDao()
        val bank = BankStore(dao)
        val seen = AtomicInteger(0)
        val initiator = UploadInitiator { _, count ->
            seen.set(count)
            List(count) { i -> fakeSession("u-$i", "rid-$i") }
        }
        val impl = newImpl(initiator, bank)

        val banked = impl.prefetchSessions(
            count = 999,
            requestTemplate = req(),
        )
        assertEquals(
            com.driveworkspace.uploader.api.DriveUploader.MAX_PREFETCH_COUNT,
            seen.get(),
        )
        assertEquals(seen.get(), banked)
    }

    // ---- helpers ---------------------------------------------------------

    private fun newImpl(initiator: UploadInitiator, bank: BankStore): DriveUploaderImpl {
        val engine = ResumableUploadEngine(
            httpClient = OkHttpClient(),
            checkpointStore = LocalCheckpointStore(FakeCheckpointDao()),
            retryPolicy = RetryPolicy(config),
            config = config,
        )
        return DriveUploaderImpl(initiator, engine, config, bank)
    }

    private fun req(
        mime: String = "application/octet-stream",
        kind: String? = null,
        size: Long = 1_000,
    ) = UploadRequest(
        fileName = "f.bin",
        mimeType = mime,
        fileSizeBytes = size,
        kindHint = kind,
    )

    private fun fakeSession(url: String, rid: String): UploadSession =
        UploadSession(
            uploadUrl = "https://stub.invalid/$url",
            remoteFileId = rid,
            expiresAt = Instant.now().plusSeconds(3600),
        )

    private fun cleanup(f: File) {
        @Suppress("ResultOfMethodCallIgnored")
        f.delete()
    }

    private suspend fun <T> List<kotlinx.coroutines.Deferred<T>>.awaitAll(): List<T> =
        map { it.await() }
}
