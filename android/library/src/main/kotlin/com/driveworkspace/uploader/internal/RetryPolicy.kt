package com.driveworkspace.uploader.internal

import com.driveworkspace.uploader.api.DriveUploaderConfig
import kotlin.math.min
import kotlin.random.Random
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds

/**
 * Pure backoff calculator. No coroutines, no clock — testable on the JVM.
 *
 * Attempt indices are 1-based; [delayFor] returns the delay to apply *before*
 * attempt N (so attempt 1 is always 0).
 */
internal class RetryPolicy(
    private val config: DriveUploaderConfig,
    private val random: Random = Random.Default,
) {
    fun delayFor(attempt: Int): Duration {
        require(attempt >= 1) { "attempt must be 1-based, was $attempt" }
        if (attempt == 1) return Duration.ZERO

        val initialMs = config.initialBackoff.inWholeMilliseconds.toDouble()
        val maxMs = config.maxBackoff.inWholeMilliseconds.toDouble()
        val raw = initialMs * pow(config.backoffMultiplier, attempt - 2)
        val capped = min(raw, maxMs)

        // Symmetric jitter: capped * (1 ± jitter)
        val jitterRange = capped * config.backoffJitter
        val jittered = capped + (random.nextDouble() * 2 - 1) * jitterRange
        val clamped = min(maxMs, jittered.coerceAtLeast(0.0))
        return clamped.toLong().milliseconds
    }

    /**
     * Honor the server's `Retry-After` header, but cap at [DriveUploaderConfig.maxBackoff].
     * Returns null if the header is absent/malformed — caller falls back to [delayFor].
     */
    fun delayForRetryAfter(headerValue: String?): Duration? {
        val seconds = headerValue?.trim()?.toLongOrNull() ?: return null
        if (seconds < 0) return null
        val ms = (seconds * 1000).coerceAtMost(config.maxBackoff.inWholeMilliseconds)
        return ms.milliseconds
    }

    private fun pow(base: Double, exp: Int): Double {
        var r = 1.0
        repeat(exp) { r *= base }
        return r
    }
}
