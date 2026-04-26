package com.driveworkspace.uploader.api

import kotlinx.coroutines.flow.Flow
import java.io.File

/**
 * The library's single public entry point.
 *
 * Each [upload] call uploads exactly one [localFile]. Concurrent calls for
 * *different* files run in parallel; concurrent calls for the *same* file
 * path are serialized internally so the local checkpoint cannot race.
 *
 * The returned [Flow] is cold: collection drives the work. Cancelling the
 * collector cancels the upload — local progress is checkpointed so a later
 * call resumes from the last acknowledged byte.
 *
 * [prefetchSessions] mints sessions in advance and stashes them in the
 * library's local bank for offline-tolerant uploads (ADR-0003). Hosts that
 * don't call it get the basic flow with no behaviour change.
 */
interface DriveUploader {
    fun upload(
        localFile: File,
        request: UploadRequest,
    ): Flow<UploadProgress>

    /**
     * Mint [count] upload sessions ahead of time and bank them locally.
     *
     * On the next [upload] call whose request matches [requestTemplate]'s
     * fingerprint (`mimeType` + `kindHint` + `fileSizeBracket`), the
     * library draws a banked session instead of calling
     * [UploadInitiator.initiate]. This lets a device with intermittent
     * backend access (but reachable Drive) keep uploading.
     *
     * Stale sessions older than 5 days are pruned on every call to this
     * method and on every draw from the bank, leaving 2 days of safety
     * margin against Drive's documented 7-day resumable-session TTL.
     *
     * Per-call cap: [MAX_PREFETCH_COUNT]. The library coerces larger
     * values down rather than failing.
     *
     * **Threading**: the underlying [UploadInitiator.initiate] call is
     * dispatched to `Dispatchers.IO` per ADR-0010. Safe to call from any
     * coroutine context.
     *
     * @return the number of sessions actually banked. Less than [count]
     *   if the initiator returned fewer than requested or if the cap
     *   trimmed the request.
     */
    suspend fun prefetchSessions(
        count: Int,
        requestTemplate: UploadRequest,
    ): Int

    companion object {
        /**
         * Server-and-client agreed cap on a single prefetch batch. Keeps
         * an accidental `prefetchSessions(Int.MAX_VALUE, ...)` from
         * minting an unbounded number of resumable sessions on the
         * backend.
         */
        const val MAX_PREFETCH_COUNT: Int = 50
    }
}
