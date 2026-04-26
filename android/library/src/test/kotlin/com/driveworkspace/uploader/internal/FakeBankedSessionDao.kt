package com.driveworkspace.uploader.internal

import com.driveworkspace.uploader.internal.checkpoint.BankedSessionDao
import com.driveworkspace.uploader.internal.checkpoint.BankedSessionEntity
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.atomic.AtomicLong

/**
 * In-memory [BankedSessionDao] for unit tests; avoids the Room+Robolectric
 * tax. The mutex on draws models Room's writer-serialisation behaviour so
 * concurrent-claim tests are meaningful.
 */
internal class FakeBankedSessionDao : BankedSessionDao {

    private val rows = LinkedHashMap<Long, BankedSessionEntity>()
    private val nextId = AtomicLong(1)
    private val drawMutex = Mutex()

    override suspend fun insertAll(rows: List<BankedSessionEntity>) {
        synchronized(this.rows) {
            for (r in rows) {
                val id = if (r.id == 0L) nextId.getAndIncrement() else r.id
                this.rows[id] = r.copy(id = id)
            }
        }
    }

    override suspend fun count(): Int = synchronized(rows) { rows.size }

    override suspend fun countMatching(mime: String, kind: String, bracket: Int): Int =
        synchronized(rows) {
            rows.values.count {
                it.mimeType == mime && it.kindHint == kind && it.fileSizeBracket == bracket
            }
        }

    override suspend fun drawOne(mime: String, kind: String, bracket: Int): BankedSessionEntity? {
        // Serialise concurrent draws — same property Room provides via its
        // writer-thread queue. Without this the test "concurrent draws never
        // return the same row" wouldn't actually probe the DAO contract.
        return drawMutex.withLock {
            val candidate = peekOldest(mime, kind, bracket) ?: return@withLock null
            val deleted = deleteById(candidate.id)
            if (deleted == 1) candidate else null
        }
    }

    override suspend fun peekOldest(mime: String, kind: String, bracket: Int): BankedSessionEntity? =
        synchronized(rows) {
            rows.values
                .filter { it.mimeType == mime && it.kindHint == kind && it.fileSizeBracket == bracket }
                .minByOrNull { it.mintedAtEpochMs }
        }

    override suspend fun deleteById(id: Long): Int = synchronized(rows) {
        if (rows.remove(id) != null) 1 else 0
    }

    override suspend fun pruneOlderThan(cutoffMs: Long): Int = synchronized(rows) {
        val ids = rows.values.filter { it.mintedAtEpochMs < cutoffMs }.map { it.id }
        ids.forEach { rows.remove(it) }
        ids.size
    }
}
