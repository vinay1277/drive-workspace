package com.driveworkspace.uploader.internal.checkpoint

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
internal interface CheckpointDao {
    @Query("SELECT * FROM upload_checkpoints WHERE localFilePath = :path LIMIT 1")
    suspend fun findByPath(path: String): CheckpointEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: CheckpointEntity)

    @Query("UPDATE upload_checkpoints SET bytesUploaded = :bytes, updatedAtEpochMs = :nowMs WHERE localFilePath = :path")
    suspend fun updateProgress(path: String, bytes: Long, nowMs: Long)

    @Query("DELETE FROM upload_checkpoints WHERE localFilePath = :path")
    suspend fun deleteByPath(path: String)
}
