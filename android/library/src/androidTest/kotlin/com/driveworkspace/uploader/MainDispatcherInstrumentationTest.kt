package com.driveworkspace.uploader

import android.os.StrictMode
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.driveworkspace.uploader.api.DriveUploaderConfig
import com.driveworkspace.uploader.api.UploadInitiator
import com.driveworkspace.uploader.api.UploadProgress
import com.driveworkspace.uploader.api.UploadRequest
import com.driveworkspace.uploader.api.UploadSession
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.time.Instant
import kotlin.random.Random

/**
 * Phase 3 instrumentation seed test enforcing ADR-0010.
 *
 * **What this catches that the JVM unit test cannot.**
 * `DriveUploaderDispatcherTest` proves on the JVM that the library
 * forces `Dispatchers.IO` for `UploadInitiator.initiate(...)`. The JVM
 * has no main-thread enforcement, so a regression that drops the
 * `withContext(Dispatchers.IO)` wrap in `DriveUploaderImpl.runUpload`
 * would still pass `DriveUploaderDispatcherTest` if the regression
 * happened to leave the lambda on a worker thread by accident — and
 * the unit test would not be able to prove the wrap holds in the
 * presence of a real Android `Looper.getMainLooper()` and
 * `StrictMode`. Both Phase 1 main-thread bugs (`35202e7`, `c03a4b1`)
 * passed JVM tests and were caught only by running the upload
 * end-to-end on the device.
 *
 * **What we test, end-to-end on the device.**
 * - `MockWebServer` in the test process answers both the initiator's
 *   POST and the engine's chunk PUT.
 * - `UploadInitiator.initiate` runs **synchronous OkHttp** with no
 *   defensive `withContext` of its own — exactly the host-implementation
 *   shape ADR-0010 was written to protect. Any host that forgets to
 *   switch dispatchers in their initiator depends on the library's
 *   outer wrap to avoid `NetworkOnMainThreadException`.
 * - The Flow is collected via `runBlocking(Dispatchers.Main) { ... }`
 *   so that the upload's coroutine starts on the real Android Main
 *   looper. That puts the library under the same dispatch conditions
 *   `viewModelScope` does.
 *
 * **Failure mode this test catches.**
 * If ADR-0010's wrap is removed from `runUpload`, the synchronous
 * OkHttp call inside `initiate` runs on the Android Main thread and
 * Android's StrictMode raises `NetworkOnMainThreadException`. The
 * library catches it as `UploadError.InitiateFailed` and emits a
 * terminal `UploadProgress.Failed` instead of `Succeeded`. The first
 * assertion below fails. The test was verified to fail-on-revert
 * before being committed (see the brief's Definition of Done).
 *
 * Brief: docs/sessions/2026-05-01-instrumentation-test.md
 */
@RunWith(AndroidJUnit4::class)
class MainDispatcherInstrumentationTest {

    private lateinit var server: MockWebServer
    private lateinit var tempFile: File

    private val config = DriveUploaderConfig(
        // 1 MB chunk; our test file is well under that, so the engine
        // ships a single chunk PUT and we only need one response queued
        // for the upload path.
        chunkSizeBytes = DriveUploaderConfig.DEFAULT_CHUNK_BYTES,
        maxAttemptsPerChunk = 1,
        maxSessionInitiations = 1,
    )

    @Before
    fun setUp() {
        server = MockWebServer().apply { start() }
        val cacheDir = InstrumentationRegistry.getInstrumentation()
            .targetContext
            .cacheDir
        tempFile = File(cacheDir, "main-dispatcher-${System.nanoTime()}.bin").apply {
            parentFile?.mkdirs()
            writeBytes(Random(42).nextBytes(SMALL_FILE_BYTES))
        }
        // Install a deterministic StrictMode ThreadPolicy on the Main
        // looper so a Network-on-Main violation actually throws
        // NetworkOnMainThreadException. Some instrumentation runners
        // ship with a permissive default that would let a broken
        // library quietly succeed; we want the assertion mechanism to
        // be present whether the runner installed one or not.
        InstrumentationRegistry.getInstrumentation().runOnMainSync {
            StrictMode.setThreadPolicy(
                StrictMode.ThreadPolicy.Builder()
                    .detectNetwork()
                    .penaltyDeath()
                    .build()
            )
        }
    }

    @After
    fun tearDown() {
        server.shutdown()
        tempFile.delete()
        // Restore a permissive policy on Main so any later code in the
        // same test process doesn't inherit our death penalty.
        InstrumentationRegistry.getInstrumentation().runOnMainSync {
            StrictMode.setThreadPolicy(StrictMode.ThreadPolicy.LAX)
        }
    }

    @Test
    fun upload_collected_on_main_succeeds_when_initiator_does_sync_okhttp() {
        // Two responses, in order:
        //   1) initiator's POST /initiate — content is irrelevant; the
        //      fake initiator only checks the response was 200 and then
        //      returns a hardcoded UploadSession.
        //   2) engine's chunk PUT to /upload-session/abc — single 200
        //      because the file fits inside one chunk.
        server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"id":"drive-x","webViewLink":null}""")
        )

        val initiateUrl = server.url("/initiate").toString()
        val sessionUrl = server.url("/upload-session/abc").toString()
        val initiatorThreadName = ThreadNameRecorder()

        // Critical: this initiator does sync OkHttp with NO inner
        // withContext. The library's outer wrap is what keeps Android's
        // StrictMode from raising NetworkOnMainThreadException.
        val initiator = UploadInitiator { _: UploadRequest, count: Int ->
            initiatorThreadName.set(Thread.currentThread().name)
            val client = OkHttpClient()
            val req = Request.Builder()
                .url(initiateUrl)
                .post("{}".toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                check(resp.isSuccessful) {
                    "initiate stub returned HTTP ${resp.code}"
                }
            }
            List(count) {
                UploadSession(
                    uploadUrl = sessionUrl,
                    remoteFileId = "drive-x",
                    expiresAt = Instant.now().plusSeconds(3600),
                )
            }
        }

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val uploader = DriveUploaderFactory.create(context, initiator, config)
        val request = UploadRequest(
            fileName = tempFile.name,
            mimeType = "application/octet-stream",
            fileSizeBytes = tempFile.length(),
        )

        // Collect on the real Android Main looper. This is what
        // viewModelScope does in production, and the dispatcher
        // condition under which both Phase 1 main-thread bugs were
        // hidden by JVM tests.
        val emissions = runBlocking(Dispatchers.Main) {
            uploader.upload(tempFile, request).toList()
        }

        // 1) Terminal emission must be Succeeded. Without ADR-0010's
        //    library-side wrap, this fails because StrictMode raises
        //    NetworkOnMainThreadException inside the initiator and the
        //    library surfaces a terminal Failed.
        val terminal = emissions.last()
        assertTrue(
            "expected terminal Succeeded, got terminal=$terminal; emissions=$emissions",
            terminal is UploadProgress.Succeeded,
        )

        // 2) The initiator's recorded thread must NOT be the Main
        //    thread. Belt-and-suspenders against a future change that
        //    lets Succeeded emit despite Main-thread initiate (e.g.
        //    if StrictMode were ever loosened).
        val name = initiatorThreadName.get()
        assertNotNull("initiator was never invoked", name)
        val nameNotNull = name!!
        assertFalse(
            "initiator must not run on the Android Main thread; was '$nameNotNull'",
            nameNotNull == "main" || nameNotNull.startsWith("main "),
        )

        // 3) Sanity: server saw the initiator POST and the chunk PUT.
        assertEquals(2, server.requestCount)
    }

    /**
     * Tiny indirection so the captured thread name survives across
     * coroutine context switches and lambda capture clearly. A plain
     * `var` would work; this just gives the assertion site a clearer
     * read site.
     */
    private class ThreadNameRecorder {
        @Volatile private var name: String? = null
        fun set(n: String) { name = n }
        fun get(): String? = name
    }

    private companion object {
        // Small enough that the engine ships exactly one chunk PUT.
        // Large enough that the file body is non-trivial.
        const val SMALL_FILE_BYTES: Int = 8 * 1024
    }
}
