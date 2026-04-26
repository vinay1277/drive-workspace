package com.driveworkspace.uploader.api

import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds
import kotlin.time.Duration.Companion.seconds

/**
 * Tunables for the upload engine. Defaults are sensible for cellular field use.
 *
 * - [chunkSizeBytes] must be a multiple of 256 KB per the Drive resumable-upload
 *   protocol (the library enforces this). 1 MB is the default.
 * - The retry budget applies *per chunk*. A session that fails [maxAttemptsPerChunk]
 *   times in a row produces a terminal [UploadProgress.Failed].
 * - On 410/404 the engine re-initiates and resets the chunk-attempt counter; the
 *   re-initiation itself is bounded by [maxSessionInitiations].
 */
data class DriveUploaderConfig(
    val chunkSizeBytes: Int = DEFAULT_CHUNK_BYTES,
    val maxAttemptsPerChunk: Int = 6,
    val maxSessionInitiations: Int = 3,
    val initialBackoff: Duration = 250.milliseconds,
    val maxBackoff: Duration = 16.seconds,
    val backoffMultiplier: Double = 2.0,
    val backoffJitter: Double = 0.25,
    val requestTimeout: Duration = 60.seconds,
) {
    init {
        require(chunkSizeBytes > 0 && chunkSizeBytes % CHUNK_GRANULARITY == 0) {
            "chunkSizeBytes ($chunkSizeBytes) must be a positive multiple of $CHUNK_GRANULARITY"
        }
        require(maxAttemptsPerChunk > 0) { "maxAttemptsPerChunk must be > 0" }
        require(maxSessionInitiations > 0) { "maxSessionInitiations must be > 0" }
        require(backoffMultiplier > 1.0) { "backoffMultiplier must be > 1.0" }
        require(backoffJitter in 0.0..1.0) { "backoffJitter must be in [0.0, 1.0]" }
    }

    companion object {
        /** Drive requires resumable chunk sizes to be a multiple of 256 KiB. */
        const val CHUNK_GRANULARITY: Int = 256 * 1024
        const val DEFAULT_CHUNK_BYTES: Int = 1024 * 1024
    }
}
