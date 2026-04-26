package com.driveworkspace.uploader.internal

import com.driveworkspace.uploader.api.DriveUploaderConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds
import kotlin.time.Duration.Companion.seconds

class RetryPolicyTest {
    private val config = DriveUploaderConfig(
        initialBackoff = 250.milliseconds,
        maxBackoff = 16.seconds,
        backoffMultiplier = 2.0,
        backoffJitter = 0.0, // deterministic for math
    )

    @Test
    fun `attempt 1 has zero delay`() {
        val policy = RetryPolicy(config, Random(0))
        assertEquals(Duration.ZERO, policy.delayFor(1))
    }

    @Test
    fun `backoff doubles up to the cap`() {
        val policy = RetryPolicy(config, Random(0))
        assertEquals(250.milliseconds, policy.delayFor(2))
        assertEquals(500.milliseconds, policy.delayFor(3))
        assertEquals(1000.milliseconds, policy.delayFor(4))
        assertEquals(2000.milliseconds, policy.delayFor(5))
        assertEquals(4000.milliseconds, policy.delayFor(6))
        assertEquals(8000.milliseconds, policy.delayFor(7))
        assertEquals(16000.milliseconds, policy.delayFor(8))
        // capped
        assertEquals(16000.milliseconds, policy.delayFor(9))
        assertEquals(16000.milliseconds, policy.delayFor(20))
    }

    @Test
    fun `jitter stays within configured band`() {
        val cfg = config.copy(backoffJitter = 0.25)
        val policy = RetryPolicy(cfg, Random(42))
        repeat(200) {
            val d = policy.delayFor(4) // base 1000ms, ±250ms
            assertTrue("delay $d below band", d.inWholeMilliseconds in 750..1250)
        }
    }

    @Test
    fun `Retry-After honored and capped at maxBackoff`() {
        val policy = RetryPolicy(config, Random(0))
        assertEquals(3000.milliseconds, policy.delayForRetryAfter("3"))
        // capped
        assertEquals(16000.milliseconds, policy.delayForRetryAfter("9999"))
    }

    @Test
    fun `Retry-After malformed returns null`() {
        val policy = RetryPolicy(config, Random(0))
        assertNull(policy.delayForRetryAfter(null))
        assertNull(policy.delayForRetryAfter(""))
        assertNull(policy.delayForRetryAfter("Wed, 01 Jan 2025 00:00:00 GMT")) // HTTP-date form unsupported
        assertNull(policy.delayForRetryAfter("-3"))
        assertNotNull(policy.delayForRetryAfter("0"))
    }
}
