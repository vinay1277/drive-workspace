package com.driveworkspace.uploader.internal.checkpoint

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

/**
 * Library-owned Room database. Encapsulated entirely inside the module —
 * the host app does not see this type and must not share it with its own
 * DB.
 *
 * Schema history:
 *  - v1: [CheckpointEntity] only.
 *  - v2: + [BankedSessionEntity] (ADR-0003 prefetch bank).
 *
 * Pre-v0.1.0 we ship a destructive migration via
 * `fallbackToDestructiveMigration`. Real migration discipline kicks in
 * at v1.0; for now, a schema bump nukes the local DB and the host app
 * re-runs any in-flight upload from scratch (the host always has the
 * source file on disk; checkpoints are an optimisation, not a source
 * of truth).
 */
@Database(
    entities = [CheckpointEntity::class, BankedSessionEntity::class],
    version = 2,
    exportSchema = false,
)
internal abstract class DriveUploadDatabase : RoomDatabase() {
    abstract fun checkpointDao(): CheckpointDao
    abstract fun bankedSessionDao(): BankedSessionDao

    companion object {
        private const val DB_NAME = "drive_uploader.db"

        @Volatile private var instance: DriveUploadDatabase? = null

        fun get(context: Context): DriveUploadDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    DriveUploadDatabase::class.java,
                    DB_NAME,
                )
                    .fallbackToDestructiveMigration()
                    .build()
                    .also { instance = it }
            }
    }
}
