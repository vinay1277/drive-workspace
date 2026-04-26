package com.driveworkspace.uploader.internal.checkpoint

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * One row per active upload, keyed by the absolute local file path.
 *
 * When a session is re-initiated (after expiry) the row is overwritten with the
 * new [uploadUrl] and [bytesUploaded] is reset.
 */
@Entity(tableName = "upload_checkpoints")
internal data class CheckpointEntity(
    @PrimaryKey val localFilePath: String,
    val uploadUrl: String,
    val remoteFileId: String,
    val totalBytes: Long,
    val bytesUploaded: Long,
    val updatedAtEpochMs: Long,
)
