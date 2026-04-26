package com.driveworkspace.uploader.internal.checkpoint

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * One row per banked resumable upload session (ADR-0003 prefetch bank).
 *
 * Sessions are minted via [com.driveworkspace.uploader.api.DriveUploader.prefetchSessions]
 * and consumed by [com.driveworkspace.uploader.api.DriveUploader.upload] on
 * fingerprint match. Rows are deleted at draw time so concurrent uploads
 * cannot accidentally reuse the same session.
 *
 * Fingerprint axes:
 *  - [mimeType]         — Drive's session-size hint and mime alignment.
 *  - [kindHint]         — host-defined bucket (`"photo"`, `"audio"`, ...).
 *                          Stored as the literal "" sentinel when null,
 *                          so the index is dense and equality is simple.
 *  - [fileSizeBracket]  — ordinal of [SizeBracket]. Avoids minting one
 *                          session per exact byte count.
 */
@Entity(
    tableName = "banked_sessions",
    indices = [
        Index(value = ["mimeType", "kindHint", "fileSizeBracket"], name = "idx_banked_fingerprint"),
        Index(value = ["mintedAtEpochMs"], name = "idx_banked_minted_at"),
    ],
)
internal data class BankedSessionEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0L,
    val uploadUrl: String,
    val remoteFileId: String,
    val expiresAtEpochMs: Long,
    val mimeType: String,
    /** Sentinel `""` represents `null` — keeps the composite index dense. */
    val kindHint: String,
    val fileSizeBracket: Int,
    val mintedAtEpochMs: Long,
) {
    companion object {
        /**
         * The on-disk representation of a `kindHint == null` request.
         * Centralised so the impl, DAO, and tests agree.
         */
        const val NULL_KIND_SENTINEL: String = ""
    }
}

/**
 * Coarse size buckets used for prefetch fingerprinting. Stored as the
 * ordinal in [BankedSessionEntity.fileSizeBracket]; new buckets must be
 * appended to preserve existing rows' meaning.
 */
internal enum class SizeBracket(val maxExclusiveBytes: Long) {
    UNDER_1_MB(1L * 1024 * 1024),
    BETWEEN_1_AND_10_MB(10L * 1024 * 1024),
    BETWEEN_10_AND_50_MB(50L * 1024 * 1024),
    OVER_50_MB(Long.MAX_VALUE);

    companion object {
        fun forBytes(bytes: Long): SizeBracket {
            require(bytes > 0) { "bytes must be positive, was $bytes" }
            return entries.first { bytes < it.maxExclusiveBytes }
        }
    }
}
