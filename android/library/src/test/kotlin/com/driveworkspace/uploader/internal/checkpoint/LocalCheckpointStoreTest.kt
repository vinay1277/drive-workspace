package com.driveworkspace.uploader.internal.checkpoint

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(sdk = [33])
class LocalCheckpointStoreTest {

    private lateinit var db: DriveUploadDatabase
    private lateinit var store: LocalCheckpointStore
    private var fakeNow = 1_000L

    @Before fun setUp() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            DriveUploadDatabase::class.java,
        ).allowMainThreadQueries().build()
        store = LocalCheckpointStore(db.checkpointDao(), nowMs = { fakeNow })
    }

    @After fun tearDown() = db.close()

    @Test fun `begin then load round-trips`() = runTest {
        store.begin("/tmp/a.bin", "https://upload/A", "remote-A", totalBytes = 10_000)
        val row = store.load("/tmp/a.bin")
        assertEquals("/tmp/a.bin", row?.localFilePath)
        assertEquals("https://upload/A", row?.uploadUrl)
        assertEquals("remote-A", row?.remoteFileId)
        assertEquals(10_000L, row?.totalBytes)
        assertEquals(0L, row?.bytesUploaded)
    }

    @Test fun `advance updates progress and timestamp`() = runTest {
        store.begin("/tmp/a.bin", "https://upload/A", "remote-A", totalBytes = 10_000)
        fakeNow = 2_000L
        store.advance("/tmp/a.bin", 4_096)
        val row = store.load("/tmp/a.bin")!!
        assertEquals(4_096L, row.bytesUploaded)
        assertEquals(2_000L, row.updatedAtEpochMs)
    }

    @Test fun `begin overwrites prior row when session changes`() = runTest {
        store.begin("/tmp/a.bin", "https://upload/A", "remote-A", totalBytes = 10_000)
        store.advance("/tmp/a.bin", 5_000)
        store.begin("/tmp/a.bin", "https://upload/B", "remote-B", totalBytes = 10_000)
        val row = store.load("/tmp/a.bin")!!
        assertEquals("https://upload/B", row.uploadUrl)
        assertEquals("remote-B", row.remoteFileId)
        assertEquals(0L, row.bytesUploaded) // reset
    }

    @Test fun `clear removes the row`() = runTest {
        store.begin("/tmp/a.bin", "https://upload/A", "remote-A", totalBytes = 10_000)
        store.clear("/tmp/a.bin")
        assertNull(store.load("/tmp/a.bin"))
    }

    @Test fun `different paths do not collide`() = runTest {
        store.begin("/tmp/a.bin", "url-a", "rid-a", 100)
        store.begin("/tmp/b.bin", "url-b", "rid-b", 200)
        assertEquals("rid-a", store.load("/tmp/a.bin")?.remoteFileId)
        assertEquals("rid-b", store.load("/tmp/b.bin")?.remoteFileId)
    }
}
