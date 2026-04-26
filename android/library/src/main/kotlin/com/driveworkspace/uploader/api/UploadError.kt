package com.driveworkspace.uploader.api

/**
 * Typed error surface for [DriveUploader].
 *
 * The library never leaks raw [Throwable]s through [UploadProgress.Failed]; one
 * of these subclasses is always emitted. Wrap unexpected exceptions in [Unknown].
 */
sealed class UploadError(
    message: String? = null,
    cause: Throwable? = null,
) : Exception(message, cause) {

    /** [UploadInitiator] threw — typically a backend/auth problem. Non-retryable by default. */
    class InitiateFailed(cause: Throwable) :
        UploadError("Failed to initiate resumable session", cause)

    /** No connectivity at the time of an attempt. Retryable. */
    class NetworkUnavailable :
        UploadError("Network unavailable")

    /** Server-side 5xx during chunk PUT. Retryable. */
    class Http5xx(val code: Int) :
        UploadError("Server error $code during upload")

    /** Client-side 4xx during chunk PUT (excluding the special-cased ones). Non-retryable. */
    class Http4xx(val code: Int, val body: String?) :
        UploadError("Client error $code during upload: ${body.orEmpty()}")

    /** The local file disappeared between scheduling and upload. Non-retryable. */
    class FileMissing :
        UploadError("Local file no longer exists")

    /** Provider returned a quota / rate-limit error that exceeded the retry budget. Retryable later. */
    class QuotaExceeded :
        UploadError("Upload quota exceeded")

    /** The resumable session expired (410 Gone / 404). The library re-initiates internally; surfaces only on terminal failure. */
    class SessionExpired :
        UploadError("Resumable session expired")

    /** Anything else. Wraps the underlying cause. */
    class Unknown(cause: Throwable) :
        UploadError(cause.message ?: "Unknown upload failure", cause)
}
