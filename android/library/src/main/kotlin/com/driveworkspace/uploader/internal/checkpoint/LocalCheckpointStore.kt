package com.driveworkspace.uploader.internal.checkpoint

/**
 * Thin wrapper that hides Room's DAO from the engine and gives us a single
 * place to add invariants (e.g. "always overwrite when session changes").
 */
internal class LocalCheckpointStore(
    private val dao: CheckpointDao,
    private val nowMs: () -> Long = System::currentTimeMillis,
) {
    suspend fun load(path: String): CheckpointEntity? = dao.findByPath(path)

    /**
     * Start a fresh checkpoint for a (possibly new) session. If a row already
     * exists for [path] it is overwritten — relevant when the session expired
     * and we just got a new URL.
     */
    suspend fun begin(
        path: String,
        uploadUrl: String,
        remoteFileId: String,
        totalBytes: Long,
    ) {
        dao.upsert(
            CheckpointEntity(
                localFilePath = path,
                uploadUrl = uploadUrl,
                remoteFileId = remoteFileId,
                totalBytes = totalBytes,
                bytesUploaded = 0L,
                updatedAtEpochMs = nowMs(),
            )
        )
    }

    suspend fun advance(path: String, bytesUploaded: Long) {
        dao.updateProgress(path, bytesUploaded, nowMs())
    }

    suspend fun clear(path: String) {
        dao.deleteByPath(path)
    }
}
