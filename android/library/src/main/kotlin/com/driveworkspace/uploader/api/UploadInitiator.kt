package com.driveworkspace.uploader.api

/**
 * Host-supplied gateway that turns an [UploadRequest] into one or more
 * resumable [UploadSession]s.
 *
 * The library never holds storage credentials. The host's backend creates
 * the resumable session(s) against the remote store (Drive, S3, Azure
 * Blob, ...) using its own service-account credential, then returns the
 * opaque upload URL(s).
 *
 * Implementations must:
 *  - Return exactly [count] sessions on success. The library treats a
 *    short list as a contract violation; hosts that genuinely cannot mint
 *    the requested batch should throw.
 *  - Be idempotent against retries (callers may invoke this repeatedly
 *    when sessions are reported expired or when prefetch is retried).
 *  - Be safe to call from a background coroutine; do not assume a UI
 *    thread.
 *
 * **Threading**: the library invokes this method from `Dispatchers.IO`
 * (per ADR-0010). Implementations may safely call blocking I/O directly
 * (e.g. synchronous OkHttp). If the implementation needs a different
 * dispatcher (e.g. `Dispatchers.Default` for CPU-bound work), use
 * `withContext` inside the implementation; the library's outer dispatch
 * becomes a no-op.
 *
 * **Batching**: when [count] > 1 the library is asking for a *prefetch*
 * batch (ADR-0003). Implementations backed by an HTTP backend should
 * forward the count to the backend in a single request rather than make
 * N round-trips — defeating that round-trip cost is the whole point of
 * prefetch. The Phase 1 reference server accepts `?count=N` and returns
 * a `{"sessions": [...]}` array; see `docs/BACKEND_CONTRACT.md`.
 */
fun interface UploadInitiator {
    /**
     * Request [count] fresh resumable upload sessions matching [request].
     *
     * @param request the request shape; for prefetch this is a *template*
     *   describing the kind of files the host plans to upload (mime,
     *   kindHint, approximate size). The library uses
     *   `(mimeType, kindHint, fileSizeBracket)` as the fingerprint when
     *   drawing from the bank.
     * @param count number of sessions to mint; defaults to 1. The library
     *   passes 1 for the synchronous upload path and N for prefetch.
     * @return a list of exactly [count] sessions.
     * @throws Exception any failure is treated by the library as a
     *   non-retryable initiate failure unless the implementation chooses
     *   to apply its own retry policy upstream.
     */
    suspend fun initiate(request: UploadRequest, count: Int): List<UploadSession>
}
