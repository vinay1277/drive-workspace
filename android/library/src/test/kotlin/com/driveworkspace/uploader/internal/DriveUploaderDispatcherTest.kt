package com.driveworkspace.uploader.internal

import com.driveworkspace.uploader.api.DriveUploaderConfig
import com.driveworkspace.uploader.api.UploadInitiator
import com.driveworkspace.uploader.api.UploadProgress
import com.driveworkspace.uploader.api.UploadRequest
import com.driveworkspace.uploader.api.UploadSession
import com.driveworkspace.uploader.internal.checkpoint.LocalCheckpointStore
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files
import kotlin.random.Random
import kotlin.time.Duration.Companion.milliseconds

/**
 * Verifies ADR-0010: the library invokes the host-supplied UploadInitiator on
 * Dispatchers.IO regardless of the collector's dispatcher.
 *
 * FIXME(phase-3): an Android instrumentation test should additionally collect
 * the upload Flow on Dispatchers.Main and exercise the chunk-PUT path; the
 * JVM-only check here cannot catch a regression on the engine side.
 */
class DriveUploaderDispatcherTest {

    private val config = DriveUploaderConfig(
        chunkSizeBytes = 256 * 1024,
        maxAttemptsPerChunk = 1,
        maxSessionInitiations = 1,
        initialBackoff = 1.milliseconds,
        maxBackoff = 1.milliseconds,
    )

    @Test
    fun `initiator runs on a non-main IO thread`() = runTest {
        var observedThreadName: String? = null
        val initiator = UploadInitiator { _: UploadRequest ->
            observedThreadName = Thread.currentThread().name
            // Short-circuit so the engine's PUT path never runs in this unit test.
            error("initiate stop — observation done")
        }

        val tempFile = Files.createTempFile("dispatcher-test", ".bin").toFile()
        tempFile.writeBytes(Random.Default.nextBytes(16))
        tempFile.deleteOnExit()

        val engine = ResumableUploadEngine(
            httpClient = OkHttpClient(),
            checkpointStore = LocalCheckpointStore(FakeCheckpointDao()),
            retryPolicy = RetryPolicy(config),
            config = config,
        )
        val impl = DriveUploaderImpl(initiator, engine, config)

        val request = UploadRequest(
            fileName = tempFile.name,
            mimeType = "application/octet-stream",
            fileSizeBytes = tempFile.length(),
        )

        val emissions = impl.upload(tempFile, request).toList()

        // Sanity: we got past Initiating and short-circuited via the thrown error.
        assertTrue(
            "expected an Initiating emission, got: $emissions",
            emissions.any { it is UploadProgress.Initiating },
        )
        assertTrue(
            "expected initiate to throw and surface as Failed, got: $emissions",
            emissions.any { it is UploadProgress.Failed },
        )

        val name = observedThreadName
        assertNotNull("initiator was never invoked", name)
        // Dispatchers.IO threads share the kotlinx coroutines default-dispatcher
        // pool and are named "DefaultDispatcher-worker-N". runTest's scheduler
        // runs the flow body on a TestCoroutineDispatcher, so seeing this name
        // proves the library forced the IO hop rather than inheriting the
        // collector's dispatcher.
        assertTrue(
            "expected initiator to run on Dispatchers.IO worker, was: $name",
            name!!.startsWith("DefaultDispatcher-worker"),
        )
    }
}
