package com.driveworkspace.uploader.internal

import com.driveworkspace.uploader.internal.checkpoint.CheckpointDao
import com.driveworkspace.uploader.internal.checkpoint.CheckpointEntity
import java.util.concurrent.ConcurrentHashMap

/** In-memory DAO for engine tests; avoids the Room+Robolectric tax. */
internal class FakeCheckpointDao : CheckpointDao {
    private val rows = ConcurrentHashMap<String, CheckpointEntity>()

    override suspend fun findByPath(path: String): CheckpointEntity? = rows[path]

    override suspend fun upsert(entity: CheckpointEntity) {
        rows[entity.localFilePath] = entity
    }

    override suspend fun updateProgress(path: String, bytes: Long, nowMs: Long) {
        rows[path]?.let { rows[path] = it.copy(bytesUploaded = bytes, updatedAtEpochMs = nowMs) }
    }

    override suspend fun deleteByPath(path: String) {
        rows.remove(path)
    }
}
