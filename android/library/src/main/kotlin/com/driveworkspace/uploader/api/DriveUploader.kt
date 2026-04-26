package com.driveworkspace.uploader.api

import kotlinx.coroutines.flow.Flow
import java.io.File

/**
 * The library's single public entry point.
 *
 * Each call uploads exactly one [localFile]. Concurrent calls for *different*
 * files run in parallel; concurrent calls for the *same* file path are
 * serialized internally so the local checkpoint cannot race.
 *
 * The returned [Flow] is cold: collection drives the work. Cancelling the
 * collector cancels the upload — local progress is checkpointed so a later
 * call resumes from the last acknowledged byte.
 */
interface DriveUploader {
    fun upload(
        localFile: File,
        request: UploadRequest,
    ): Flow<UploadProgress>
}
