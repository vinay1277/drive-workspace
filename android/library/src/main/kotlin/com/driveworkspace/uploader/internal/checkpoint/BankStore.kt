package com.driveworkspace.uploader.internal.checkpoint

import com.driveworkspace.uploader.api.UploadRequest
import com.driveworkspace.uploader.api.UploadSession
import java.time.Instant
import kotlin.time.Duration
import kotlin.time.Duration.Companion.days

/**
 * Thin wrapper over [BankedSessionDao] that holds the prefetch-bank
 * invariants in one place:
 *
 *  - Stale rows are pruned on every bank-touching call (ADR-0003: 5-day
 *    TTL, leaving 2 days of margin against Drive's 7-day session TTL).
 *  - Fingerprint construction is centralised so the prefetch path and
 *    the upload path agree byte-for-byte on what counts as a match.
 *  - The on-disk null-kind sentinel is private to this layer; callers
 *    pass `UploadRequest.kindHint` directly.
 */
internal class BankStore(
    private val dao: BankedSessionDao,
    private val nowMs: () -> Long = System::currentTimeMillis,
    private val staleAfter: Duration = DEFAULT_STALE_AFTER,
) {
    /**
     * Insert [sessions] into the bank using [template] for fingerprint
     * axes. Prunes stale rows first.
     *
     * Returns the number of rows inserted (== `sessions.size`).
     */
    suspend fun bank(
        template: UploadRequest,
        sessions: List<UploadSession>,
    ): Int {
        if (sessions.isEmpty()) return 0
        prune()
        val now = nowMs()
        val fp = fingerprint(template)
        val rows = sessions.map { s ->
            BankedSessionEntity(
                uploadUrl = s.uploadUrl,
                remoteFileId = s.remoteFileId,
                expiresAtEpochMs = s.expiresAt.toEpochMilli(),
                mimeType = fp.mime,
                kindHint = fp.kind,
                fileSizeBracket = fp.bracket,
                mintedAtEpochMs = now,
            )
        }
        dao.insertAll(rows)
        return rows.size
    }

    /**
     * Atomically claim and return one banked session matching [request]'s
     * fingerprint, or null if none. Prunes stale rows first.
     */
    suspend fun tryDraw(request: UploadRequest): UploadSession? {
        prune()
        val fp = fingerprint(request)
        val row = dao.drawOne(fp.mime, fp.kind, fp.bracket) ?: return null
        return UploadSession(
            uploadUrl = row.uploadUrl,
            remoteFileId = row.remoteFileId,
            expiresAt = Instant.ofEpochMilli(row.expiresAtEpochMs),
        )
    }

    suspend fun count(): Int = dao.count()

    private suspend fun prune() {
        val cutoff = nowMs() - staleAfter.inWholeMilliseconds
        dao.pruneOlderThan(cutoff)
    }

    private data class Fingerprint(val mime: String, val kind: String, val bracket: Int)

    private fun fingerprint(req: UploadRequest): Fingerprint = Fingerprint(
        mime = req.mimeType,
        kind = req.kindHint ?: BankedSessionEntity.NULL_KIND_SENTINEL,
        bracket = SizeBracket.forBytes(req.fileSizeBytes).ordinal,
    )

    companion object {
        /** ADR-0003: 5 days; Drive's 7-day session TTL minus 2 days margin. */
        val DEFAULT_STALE_AFTER: Duration = 5.days
    }
}
