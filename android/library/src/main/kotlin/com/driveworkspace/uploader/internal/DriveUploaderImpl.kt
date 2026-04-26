package com.driveworkspace.uploader.internal

import com.driveworkspace.uploader.api.DriveUploader
import com.driveworkspace.uploader.api.DriveUploaderConfig
import com.driveworkspace.uploader.api.UploadError
import com.driveworkspace.uploader.api.UploadInitiator
import com.driveworkspace.uploader.api.UploadProgress
import com.driveworkspace.uploader.api.UploadRequest
import com.driveworkspace.uploader.api.UploadSession
import com.driveworkspace.uploader.internal.checkpoint.BankStore
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
    private val bank: BankStore,
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

    override suspend fun prefetchSessions(
        count: Int,
        requestTemplate: UploadRequest,
    ): Int {
        if (count <= 0) return 0
        val capped = count.coerceAtMost(DriveUploader.MAX_PREFETCH_COUNT)
        if (capped < count) {
            Timber.tag(TAG).w(
                "prefetchSessions count=%d capped at %d (DriveUploader.MAX_PREFETCH_COUNT)",
                count, capped,
            )
        }
        val sessions = try {
            withContext(Dispatchers.IO) { initiator.initiate(requestTemplate, capped) }
        } catch (t: Throwable) {
            Timber.tag(TAG).w(t, "prefetchSessions: initiator failed")
            return 0
        }
        if (sessions.isEmpty()) return 0
        if (sessions.size != capped) {
            Timber.tag(TAG).w(
                "prefetchSessions: requested %d, initiator returned %d; banking what we got",
                capped, sessions.size,
            )
        }
        return bank.bank(requestTemplate, sessions)
    }

    private fun runUpload(localFile: File, request: UploadRequest): Flow<UploadProgress> = flow {
        if (!localFile.exists()) {
            emit(UploadProgress.Failed(UploadError.FileMissing(), isRetryable = false))
            return@flow
        }
        var initAttempt = 0
        // Once we use a banked session and it expires, we fall through to live
        // initiate on the next loop iteration — never re-draw, since the bank
        // entry that just expired is unlikely to be the only stale one.
        var bankExhausted = false
        while (true) {
            initAttempt++
            emit(UploadProgress.Initiating(initAttempt))
            val session = try {
                obtainSession(request, allowBank = !bankExhausted)
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
                    bankExhausted = true
                    Timber.tag(TAG).i("session expired — re-initiating (attempt=%d)", initAttempt + 1)
                    // Loop and re-initiate live.
                }
                is ResumableUploadEngine.Outcome.Failed -> {
                    emit(UploadProgress.Failed(outcome.error, isRetryable = isRetryable(outcome.error)))
                    return@flow
                }
            }
        }
    }

    /**
     * Try the bank first (if allowed); fall through to a live initiator
     * call dispatched to IO per ADR-0010. The bank lookup itself runs on
     * IO too — Room is suspend-friendly but its query work shouldn't run
     * on Main, and the prune step can touch the DB writer.
     */
    private suspend fun obtainSession(
        request: UploadRequest,
        allowBank: Boolean,
    ): UploadSession {
        if (allowBank) {
            val banked = withContext(Dispatchers.IO) { bank.tryDraw(request) }
            if (banked != null) {
                Timber.tag(TAG).i("upload using banked session")
                return banked
            }
        }
        val sessions = withContext(Dispatchers.IO) { initiator.initiate(request, 1) }
        check(sessions.isNotEmpty()) {
            "UploadInitiator.initiate returned empty list for count=1"
        }
        return sessions.first()
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
