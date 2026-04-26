package com.driveworkspace.uploader.internal.checkpoint

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

/**
 * Library-owned Room database. Encapsulated entirely inside the module — the
 * host app does not see this type and must not share it with its own DB.
 *
 * Ships exactly one table ([CheckpointEntity]). If/when we need more
 * (e.g. a queue), a new entity goes here.
 */
@Database(
    entities = [CheckpointEntity::class],
    version = 1,
    exportSchema = false,
)
internal abstract class DriveUploadDatabase : RoomDatabase() {
    abstract fun checkpointDao(): CheckpointDao

    companion object {
        private const val DB_NAME = "drive_uploader.db"

        @Volatile private var instance: DriveUploadDatabase? = null

        fun get(context: Context): DriveUploadDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    DriveUploadDatabase::class.java,
                    DB_NAME,
                ).build().also { instance = it }
            }
    }
}
