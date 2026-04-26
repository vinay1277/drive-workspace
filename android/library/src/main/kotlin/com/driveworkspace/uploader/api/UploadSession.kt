package com.driveworkspace.uploader.api

import java.time.Instant

/**
 * Resumable upload session as returned by the host's [UploadInitiator].
 *
 * - [uploadUrl] is the resumable PUT endpoint (e.g. a Drive resumable session URL).
 *   The library treats it as opaque.
 * - [remoteFileId] identifies the file in the remote store. Echoed back to the
 *   host on [UploadProgress.Succeeded].
 * - [expiresAt] is informational; if the URL has actually expired, the library
 *   detects it via the 410/404 response and re-initiates.
 */
data class UploadSession(
    val uploadUrl: String,
    val remoteFileId: String,
    val expiresAt: Instant,
) {
    init {
        require(uploadUrl.isNotBlank()) { "uploadUrl must not be blank" }
        require(remoteFileId.isNotBlank()) { "remoteFileId must not be blank" }
    }
}
