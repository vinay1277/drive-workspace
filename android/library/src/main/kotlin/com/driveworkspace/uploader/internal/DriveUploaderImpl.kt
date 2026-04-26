package com.driveworkspace.uploader.internal

import com.driveworkspace.uploader.api.DriveUploader
import com.driveworkspace.uploader.api.DriveUploaderConfig
import com.driveworkspace.uploader.api.UploadError
import com.driveworkspace.uploader.api.UploadInitiator
import com.driveworkspace.uploader.api.UploadProgress
import com.driveworkspace.uploader.api.UploadRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.io.File
import java.util.concurrent.ConcurrentHashMap

internal class DriveUploaderImpl(
    private val initiator: UploadInitiator,
    private val engine: ResumableUploadEngine,
    private val config: DriveUploaderConfig,
) : DriveUploader {

    /** Single-flight per local file path. Different files upload in parallel. */
    private val perPathLocks = ConcurrentHashMap<String, Mutex>()

    override fun upload(localFile: File, request: UploadRequest): Flow<UploadProgress> = flow {
        val path = localFile.absolutePath
        val lock = perPathLocks.computeIfAbsent(path) { Mutex() }
        lock.withLock {
            try {
                runUpload(localFile, request).collect { emit(it) }
            } finally {
                // Best-effort cleanup; another caller for the same path will reinsert.
                perPathLocks.remove(path, lock)
            }
        }
    }

    private fun runUpload(localFile: File, request: UploadRequest): Flow<UploadProgress> = flow {
        if (!localFile.exists()) {
            emit(UploadProgress.Failed(UploadError.FileMissing(), isRetryable = false))
            return@flow
        }
        var initAttempt = 0
        while (true) {
            initAttempt++
            emit(UploadProgress.Initiating(initAttempt))
            val session = try {
                withContext(Dispatchers.IO) { initiator.initiate(request) }
            } catch (t: Throwable) {
                Timber.tag(TAG).w(t, "initiate failed")
                emit(UploadProgress.Failed(UploadError.InitiateFailed(t), isRetryable = true))
                return@flow
            }

            val outcome = engine.upload(
                file = localFile,
                session = session,
                mimeType = request.mimeType,
            ) { uploaded, total ->
                emit(UploadProgress.Transferring(uploaded, total))
            }

            when (outcome) {
                is ResumableUploadEngine.Outcome.Success -> {
                    emit(UploadProgress.Succeeded(session.remoteFileId, outcome.webViewLink))
                    return@flow
                }
                ResumableUploadEngine.Outcome.SessionExpired -> {
                    if (initAttempt >= config.maxSessionInitiations) {
                        emit(UploadProgress.Failed(UploadError.SessionExpired(), isRetryable = true))
                        return@flow
                    }
                    Timber.tag(TAG).i("session expired — re-initiating (attempt=%d)", initAttempt + 1)
                    // Loop and re-initiate.
                }
                is ResumableUploadEngine.Outcome.Failed -> {
                    emit(UploadProgress.Failed(outcome.error, isRetryable = isRetryable(outcome.error)))
                    return@flow
                }
            }
        }
    }

    private fun isRetryable(error: UploadError): Boolean = when (error) {
        is UploadError.NetworkUnavailable,
        is UploadError.Http5xx,
        is UploadError.QuotaExceeded,
        is UploadError.SessionExpired -> true
        is UploadError.Http4xx,
        is UploadError.FileMissing -> false
        is UploadError.InitiateFailed,
        is UploadError.Unknown -> true
    }

    private companion object {
        const val TAG = "DriveUpload"
    }
}
