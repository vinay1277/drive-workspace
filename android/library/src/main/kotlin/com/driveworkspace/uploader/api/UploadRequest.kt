package com.driveworkspace.uploader.api

/**
 * Description of a single file the host wants the library to upload.
 *
 * [metadata] is opaque to the library and forwarded as-is to [UploadInitiator].
 * Use it to carry whatever the host's backend needs to route the file (target
 * Drive folder id, ownership claims, business identifiers, etc.).
 */
data class UploadRequest(
    val fileName: String,
    val mimeType: String,
    val fileSizeBytes: Long,
    val metadata: Map<String, String> = emptyMap(),
) {
    init {
        require(fileName.isNotBlank()) { "fileName must not be blank" }
        require(mimeType.isNotBlank()) { "mimeType must not be blank" }
        require(fileSizeBytes > 0) { "fileSizeBytes must be positive, was $fileSizeBytes" }
    }
}
