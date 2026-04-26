package com.driveworkspace.uploader.api

/**
 * Host-supplied gateway that turns an [UploadRequest] into a resumable [UploadSession].
 *
 * The library never holds storage credentials. The host's backend creates the
 * resumable session against the remote store (Drive, S3, Azure Blob, ...) using
 * its own service-account credential, then returns the opaque upload URL.
 *
 * Implementations must:
 *  - Be idempotent against retries (callers may invoke this repeatedly when a
 *    session is reported expired).
 *  - Be safe to call from a background coroutine; do not assume a UI thread.
 *
 * **Threading**: the library invokes this method from `Dispatchers.IO`.
 * Implementations may safely call blocking I/O directly (e.g. synchronous
 * OkHttp). If the implementation needs a different dispatcher (e.g.
 * `Dispatchers.Default` for CPU-bound work), use `withContext` inside the
 * implementation; the library's outer dispatch becomes a no-op.
 */
fun interface UploadInitiator {
    /**
     * Request a fresh resumable upload session.
     *
     * @throws Exception any failure is treated by the library as a non-retryable
     *  initiate failure unless the implementation chooses to apply its own retry
     *  policy upstream.
     */
    suspend fun initiate(request: UploadRequest): UploadSession
}
