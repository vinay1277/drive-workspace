package com.driveworkspace.uploader.api

/**
 * Description of a single file the host wants the library to upload.
 *
 * [metadata] is opaque to the library and forwarded as-is to [UploadInitiator].
 * Use it to carry whatever the host's backend needs to route the file (target
 * Drive folder id, ownership claims, business identifiers, etc.).
 *
 * [kindHint] is a typed slot used by the prefetch bank (ADR-0003) to
 * fingerprint sessions for reuse: two requests with the same `(mimeType,
 * kindHint, fileSizeBracket)` triple are considered interchangeable from the
 * bank's perspective. Hosts that don't use prefetch can leave it null. The
 * library does not interpret the value — host-defined buckets like `"photo"`,
 * `"audio"`, `"video"`, or `"survey-attachment"` work; consistency between
 * the prefetch template and the eventual upload is what matters.
 */
data class UploadRequest(
    val fileName: String,
    val mimeType: String,
    val fileSizeBytes: Long,
    val metadata: Map<String, String> = emptyMap(),
    val kindHint: String? = null,
) {
    init {
        require(fileName.isNotBlank()) { "fileName must not be blank" }
        require(mimeType.isNotBlank()) { "mimeType must not be blank" }
        require(fileSizeBytes > 0) { "fileSizeBytes must be positive, was $fileSizeBytes" }
    }
}
