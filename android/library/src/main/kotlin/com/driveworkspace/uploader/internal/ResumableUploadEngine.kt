package com.driveworkspace.uploader.internal

import com.driveworkspace.uploader.api.DriveUploaderConfig
import com.driveworkspace.uploader.api.UploadError
import com.driveworkspace.uploader.api.UploadSession
import com.driveworkspace.uploader.internal.checkpoint.LocalCheckpointStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.runInterruptible
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.Response
import okio.BufferedSink
import timber.log.Timber
import java.io.File
import java.io.IOException
import java.io.RandomAccessFile

/**
 * Runs the resumable PUT loop for a single [UploadSession] against [session.uploadUrl].
 *
 * Outcomes are deliberately enumerated; the caller decides whether to re-initiate
 * (on [Outcome.SessionExpired]) or terminate (on [Outcome.Failed] / [Outcome.Success]).
 */
internal class ResumableUploadEngine(
    private val httpClient: OkHttpClient,
    private val checkpointStore: LocalCheckpointStore,
    private val retryPolicy: RetryPolicy,
    private val config: DriveUploaderConfig,
) {
    sealed interface Outcome {
        data class Success(val webViewLink: String?) : Outcome
        data object SessionExpired : Outcome
        data class Failed(val error: UploadError) : Outcome
    }

    /**
     * @param onProgress invoked at chunk boundaries with (bytesUploaded, totalBytes)
     */
    suspend fun upload(
        file: File,
        session: UploadSession,
        mimeType: String,
        onProgress: suspend (Long, Long) -> Unit,
    ): Outcome {
        if (!file.exists()) return Outcome.Failed(UploadError.FileMissing())
        val total = file.length()

        // Reconcile checkpoint with the session URL we were just handed.
        val existing = checkpointStore.load(file.absolutePath)
        var bytesUploaded = if (existing != null && existing.uploadUrl == session.uploadUrl) {
            existing.bytesUploaded
        } else {
            checkpointStore.begin(file.absolutePath, session.uploadUrl, session.remoteFileId, total)
            0L
        }

        // If we believe we're resuming, ask the server what it has — local checkpoints
        // can drift if the previous run crashed mid-flight.
        if (bytesUploaded > 0) {
            when (val q = queryServerOffset(session.uploadUrl, total)) {
                is OffsetQuery.Incomplete -> bytesUploaded = q.bytesAcknowledged
                is OffsetQuery.Complete -> {
                    checkpointStore.clear(file.absolutePath)
                    return Outcome.Success(webViewLink = q.webViewLink)
                }
                OffsetQuery.SessionGone -> return Outcome.SessionExpired
                is OffsetQuery.Failed -> return Outcome.Failed(q.error)
            }
            checkpointStore.advance(file.absolutePath, bytesUploaded)
        }

        onProgress(bytesUploaded, total)

        RandomAccessFile(file, "r").use { raf ->
            while (bytesUploaded < total) {
                val chunkStart = bytesUploaded
                val chunkEnd = minOf(chunkStart + config.chunkSizeBytes, total) - 1
                val chunkLen = (chunkEnd - chunkStart + 1).toInt()

                when (val r = putChunkWithRetries(session.uploadUrl, raf, chunkStart, chunkEnd, total, mimeType)) {
                    is ChunkResult.Continue -> {
                        bytesUploaded = r.serverAck + 1
                        checkpointStore.advance(file.absolutePath, bytesUploaded)
                        onProgress(bytesUploaded, total)
                        Timber.tag(TAG).d("chunk ok start=%d end=%d ack=%d", chunkStart, chunkEnd, r.serverAck)
                    }
                    is ChunkResult.Done -> {
                        checkpointStore.clear(file.absolutePath)
                        onProgress(total, total)
                        return Outcome.Success(r.webViewLink)
                    }
                    ChunkResult.SessionGone -> return Outcome.SessionExpired
                    is ChunkResult.Failed -> return Outcome.Failed(r.error)
                }
                // Defensive: avoid spinning if the server keeps acknowledging less than we send.
                if (chunkLen == 0) return Outcome.Failed(UploadError.Unknown(IllegalStateException("Zero-length chunk")))
            }
        }
        // Fell out without ever seeing a 200 — should not happen if sizes line up.
        return Outcome.Failed(UploadError.Unknown(IllegalStateException("Upload completed without final 200")))
    }

    // ---- internals --------------------------------------------------------

    private sealed interface OffsetQuery {
        data class Incomplete(val bytesAcknowledged: Long) : OffsetQuery
        data class Complete(val webViewLink: String?) : OffsetQuery
        data object SessionGone : OffsetQuery
        data class Failed(val error: UploadError) : OffsetQuery
    }

    private suspend fun queryServerOffset(url: String, total: Long): OffsetQuery {
        val req = Request.Builder()
            .url(url)
            .header("Content-Range", "bytes */$total")
            .header("Content-Length", "0")
            .put(EmptyBody)
            .build()
        return try {
            withResponseOnIO(req) { resp ->
                when {
                    resp.code == 308 -> OffsetQuery.Incomplete(parseRangeUpper(resp.header("Range")) + 1)
                    resp.isSuccessful -> OffsetQuery.Complete(extractWebViewLink(resp))
                    resp.code == 410 || resp.code == 404 -> OffsetQuery.SessionGone
                    resp.code in 500..599 -> OffsetQuery.Failed(UploadError.Http5xx(resp.code))
                    else -> OffsetQuery.Failed(UploadError.Http4xx(resp.code, resp.peekBody(MAX_ERR_BODY).string()))
                }
            }
        } catch (e: IOException) {
            OffsetQuery.Failed(UploadError.NetworkUnavailable())
        }
    }

    private sealed interface ChunkResult {
        data class Continue(val serverAck: Long) : ChunkResult
        data class Done(val webViewLink: String?) : ChunkResult
        data object SessionGone : ChunkResult
        data class Failed(val error: UploadError) : ChunkResult
    }

    private suspend fun putChunkWithRetries(
        url: String,
        raf: RandomAccessFile,
        start: Long,
        end: Long,
        total: Long,
        mimeType: String,
    ): ChunkResult {
        var attempt = 1
        while (true) {
            if (attempt > 1) {
                val delayMs = retryPolicy.delayFor(attempt).inWholeMilliseconds
                Timber.tag(TAG).d("chunk retry attempt=%d delayMs=%d", attempt, delayMs)
                delay(delayMs)
            }
            val body = RangeFileBody(raf, start, (end - start + 1).toInt(), mimeType.toMediaType())
            val req = Request.Builder()
                .url(url)
                .header("Content-Range", "bytes $start-$end/$total")
                .put(body)
                .build()
            val outcome: ChunkResult = try {
                withResponseOnIO(req) { resp -> classifyChunkResponse(resp) }
            } catch (e: IOException) {
                ChunkResult.Failed(UploadError.NetworkUnavailable())
            }

            when (outcome) {
                is ChunkResult.Continue, is ChunkResult.Done, ChunkResult.SessionGone -> return outcome
                is ChunkResult.Failed -> {
                    val retryable = outcome.error is UploadError.Http5xx ||
                        outcome.error is UploadError.NetworkUnavailable ||
                        outcome.error is UploadError.QuotaExceeded
                    if (!retryable || attempt >= config.maxAttemptsPerChunk) return outcome
                    attempt++
                }
            }
        }
    }

    private fun classifyChunkResponse(resp: Response): ChunkResult = when {
        resp.code == 308 -> {
            val ack = parseRangeUpper(resp.header("Range"))
            ChunkResult.Continue(serverAck = ack)
        }
        resp.isSuccessful -> ChunkResult.Done(extractWebViewLink(resp))
        resp.code == 410 || resp.code == 404 -> ChunkResult.SessionGone
        resp.code == 429 -> ChunkResult.Failed(UploadError.QuotaExceeded())
        resp.code in 500..599 -> ChunkResult.Failed(UploadError.Http5xx(resp.code))
        else -> ChunkResult.Failed(UploadError.Http4xx(resp.code, resp.peekBody(MAX_ERR_BODY).string()))
    }

    /**
     * Execute [req] and run [block] against the [Response] entirely on
     * `Dispatchers.IO`, including the implicit `Response.close()` that
     * `.use { … }` performs.
     *
     * This is stricter than the historical `executeAsync` helper, which
     * only forced `httpClient.newCall(req).execute()` onto IO and
     * resumed on the caller's dispatcher (Main, in production
     * `viewModelScope` collection). That left subsequent body-reading
     * calls — `Response.peekBody().string()`, `extractWebViewLink`,
     * the `.use { }` block's `close()` — running on the caller's
     * dispatcher; on Main, those drain remaining socket bytes and
     * trigger `NetworkOnMainThreadException` via Android's StrictMode.
     * The Phase 3 instrumentation test caught this; ADR-0010 covers
     * `UploadInitiator.initiate` symmetrically and this is the same
     * defensive policy applied to chunk-PUT response handling.
     */
    private suspend fun <R> withResponseOnIO(
        req: Request,
        block: (Response) -> R,
    ): R = runInterruptible(Dispatchers.IO) {
        httpClient.newCall(req).execute().use(block)
    }

    /** Parses a Drive-style `Range: bytes=0-N` header, returning N. Returns -1 if absent/malformed. */
    private fun parseRangeUpper(header: String?): Long {
        if (header.isNullOrBlank()) return -1
        val eq = header.indexOf('=')
        val dash = header.indexOf('-', startIndex = if (eq >= 0) eq else 0)
        if (dash <= 0) return -1
        return header.substring(dash + 1).trim().toLongOrNull() ?: -1
    }

    private fun extractWebViewLink(resp: Response): String? {
        val body = resp.peekBody(MAX_BODY).string()
        // Cheap regex — we don't depend on a JSON parser for this one optional field.
        val m = WEB_VIEW_LINK_REGEX.find(body) ?: return null
        return m.groupValues.getOrNull(1)
    }

    private object EmptyBody : RequestBody() {
        override fun contentType() = "application/octet-stream".toMediaType()
        override fun contentLength() = 0L
        override fun writeTo(sink: BufferedSink) { /* nothing */ }
    }

    private class RangeFileBody(
        private val raf: RandomAccessFile,
        private val offset: Long,
        private val length: Int,
        private val mediaType: okhttp3.MediaType,
    ) : RequestBody() {
        override fun contentType() = mediaType
        override fun contentLength(): Long = length.toLong()
        override fun isOneShot() = false
        override fun writeTo(sink: BufferedSink) {
            raf.seek(offset)
            val buf = ByteArray(BUFFER_BYTES)
            var remaining = length
            while (remaining > 0) {
                val toRead = minOf(buf.size, remaining)
                val read = raf.read(buf, 0, toRead)
                if (read <= 0) throw IOException("Unexpected EOF reading file at offset=$offset remaining=$remaining")
                sink.write(buf, 0, read)
                remaining -= read
            }
        }
        companion object {
            private const val BUFFER_BYTES = 64 * 1024
        }
    }

    private companion object {
        const val TAG = "DriveUpload"
        const val MAX_ERR_BODY = 4 * 1024L
        const val MAX_BODY = 16 * 1024L
        val WEB_VIEW_LINK_REGEX = "\"webViewLink\"\\s*:\\s*\"([^\"]+)\"".toRegex()
    }
}
