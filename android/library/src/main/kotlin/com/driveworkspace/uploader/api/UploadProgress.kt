package com.driveworkspace.uploader.api

/**
 * Progress events emitted while a single file uploads.
 *
 * The [Flow] returned by [DriveUploader.upload] always emits exactly one
 * terminal event ([Succeeded] or [Failed]) before completing.
 */
sealed interface UploadProgress {
    /** A new resumable session is being negotiated with [UploadInitiator]. */
    data class Initiating(val attempt: Int) : UploadProgress

    /** Bytes are flowing. Emitted at chunk boundaries. */
    data class Transferring(
        val bytesUploaded: Long,
        val bytesTotal: Long,
    ) : UploadProgress {
        val fraction: Float get() =
            if (bytesTotal <= 0) 0f else (bytesUploaded.toDouble() / bytesTotal).toFloat()
    }

    /** Terminal: upload completed; [remoteFileId] echoes the session value. */
    data class Succeeded(
        val remoteFileId: String,
        val webViewLink: String?,
    ) : UploadProgress

    /** Terminal: upload failed. [isRetryable] tells the host whether to schedule a retry. */
    data class Failed(
        val error: UploadError,
        val isRetryable: Boolean,
    ) : UploadProgress
}
