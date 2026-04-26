package com.driveworkspace.uploader.work

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.driveworkspace.uploader.api.DriveUploader
import com.driveworkspace.uploader.api.UploadProgress
import com.driveworkspace.uploader.api.UploadRequest
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.lastOrNull
import timber.log.Timber
import java.io.File

/**
 * Optional WorkManager entry point. Hosts may use this directly via
 * [androidx.work.OneTimeWorkRequestBuilder], or implement their own Worker that
 * calls [DriveUploader.upload] — both paths are supported.
 *
 * Inputs:
 *  - [KEY_FILE_PATH]      (String) absolute path of the file to upload
 *  - [KEY_FILE_NAME]      (String) remote file name
 *  - [KEY_MIME_TYPE]      (String) MIME type
 *  - [KEY_FILE_SIZE]      (Long) size in bytes
 *  - [KEY_METADATA_KEYS]  (String[]) metadata keys
 *  - [KEY_METADATA_VALUES](String[]) metadata values, parallel to keys
 *
 * Outputs (on success):
 *  - [KEY_REMOTE_FILE_ID] (String)
 *  - [KEY_WEB_VIEW_LINK]  (String, nullable)
 */
@HiltWorker
class DriveUploadWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val uploader: DriveUploader,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val path = inputData.getString(KEY_FILE_PATH)
            ?: return Result.failure()
        val request = UploadRequest(
            fileName = inputData.getString(KEY_FILE_NAME) ?: return Result.failure(),
            mimeType = inputData.getString(KEY_MIME_TYPE) ?: return Result.failure(),
            fileSizeBytes = inputData.getLong(KEY_FILE_SIZE, -1L)
                .takeIf { it > 0 } ?: return Result.failure(),
            metadata = readMetadata(),
        )

        var terminal: UploadProgress? = null
        try {
            uploader.upload(File(path), request).collect { progress ->
                if (progress is UploadProgress.Succeeded || progress is UploadProgress.Failed) {
                    terminal = progress
                }
            }
        } catch (t: Throwable) {
            Timber.tag(TAG).w(t, "Worker upload threw")
            return Result.retry()
        }

        return when (val t = terminal) {
            is UploadProgress.Succeeded -> Result.success(
                workDataOf(
                    KEY_REMOTE_FILE_ID to t.remoteFileId,
                    KEY_WEB_VIEW_LINK to t.webViewLink,
                )
            )
            is UploadProgress.Failed -> if (t.isRetryable) Result.retry() else Result.failure()
            else -> Result.failure()
        }
    }

    private fun readMetadata(): Map<String, String> {
        val keys = inputData.getStringArray(KEY_METADATA_KEYS) ?: return emptyMap()
        val values = inputData.getStringArray(KEY_METADATA_VALUES) ?: return emptyMap()
        if (keys.size != values.size) return emptyMap()
        return keys.zip(values).toMap()
    }

    companion object {
        private const val TAG = "DriveUploadWorker"

        const val KEY_FILE_PATH = "file_path"
        const val KEY_FILE_NAME = "file_name"
        const val KEY_MIME_TYPE = "mime_type"
        const val KEY_FILE_SIZE = "file_size"
        const val KEY_METADATA_KEYS = "metadata_keys"
        const val KEY_METADATA_VALUES = "metadata_values"

        const val KEY_REMOTE_FILE_ID = "remote_file_id"
        const val KEY_WEB_VIEW_LINK = "web_view_link"
    }
}
