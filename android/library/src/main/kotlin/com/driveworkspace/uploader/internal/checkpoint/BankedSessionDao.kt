package com.driveworkspace.uploader.internal.checkpoint

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction

@Dao
internal interface BankedSessionDao {

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertAll(rows: List<BankedSessionEntity>)

    @Query("SELECT COUNT(*) FROM banked_sessions")
    suspend fun count(): Int

    @Query("SELECT COUNT(*) FROM banked_sessions WHERE mimeType = :mime AND kindHint = :kind AND fileSizeBracket = :bracket")
    suspend fun countMatching(mime: String, kind: String, bracket: Int): Int

    /**
     * Atomic claim: pick the oldest banked session matching the
     * fingerprint, delete it, return it. Room serialises writes through
     * one writer, so two coroutines calling this concurrently each see a
     * different row (or null).
     *
     * Sentinel `""` for `kindHint` represents the null-kindHint request;
     * see [BankedSessionEntity.NULL_KIND_SENTINEL].
     */
    @Transaction
    suspend fun drawOne(mime: String, kind: String, bracket: Int): BankedSessionEntity? {
        val candidate = peekOldest(mime, kind, bracket) ?: return null
        val rowsDeleted = deleteById(candidate.id)
        return if (rowsDeleted == 1) candidate else null
    }

    @Query(
        "SELECT * FROM banked_sessions " +
            "WHERE mimeType = :mime AND kindHint = :kind AND fileSizeBracket = :bracket " +
            "ORDER BY mintedAtEpochMs ASC LIMIT 1"
    )
    suspend fun peekOldest(mime: String, kind: String, bracket: Int): BankedSessionEntity?

    @Query("DELETE FROM banked_sessions WHERE id = :id")
    suspend fun deleteById(id: Long): Int

    @Query("DELETE FROM banked_sessions WHERE mintedAtEpochMs < :cutoffMs")
    suspend fun pruneOlderThan(cutoffMs: Long): Int
}
