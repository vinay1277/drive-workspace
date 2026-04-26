# `:library` — Resumable Drive Upload Library

A reusable Android library for uploading files to Google Drive (or any other
backend that exposes a resumable PUT URL) with full offline-survival semantics:
chunked transfer, range-based resume across crashes, exponential backoff with
jitter, and session re-initiation on expiry.

The library never holds storage credentials. The host's backend mints
resumable upload URLs against its own service account; the library streams
bytes to those URLs.

---

## Public API (the whole surface)

```kotlin
interface DriveUploader {
    fun upload(localFile: File, request: UploadRequest): Flow<UploadProgress>
}

fun interface UploadInitiator {
    suspend fun initiate(request: UploadRequest): UploadSession
}

data class UploadRequest(
    val fileName: String,
    val mimeType: String,
    val fileSizeBytes: Long,
    val metadata: Map<String, String> = emptyMap(),
)

data class UploadSession(
    val uploadUrl: String,
    val remoteFileId: String,
    val expiresAt: Instant,
)

sealed interface UploadProgress {
    data class Initiating(val attempt: Int) : UploadProgress
    data class Transferring(val bytesUploaded: Long, val bytesTotal: Long) : UploadProgress
    data class Succeeded(val remoteFileId: String, val webViewLink: String?) : UploadProgress
    data class Failed(val error: UploadError, val isRetryable: Boolean) : UploadProgress
}

sealed class UploadError : Exception() { /* see source */ }
```

That's it. Everything else is `internal`.

---

## How to integrate in 10 minutes

### 1. Add the dependency

```kotlin
// app/build.gradle.kts
dependencies {
    implementation(project(":library"))
}
```

### 2. Implement `UploadInitiator`

The library calls this every time it needs a fresh resumable session. Your
implementation hits your own backend, which mints the Drive URL with a service
account credential.

```kotlin
class HostUploadInitiator @Inject constructor(
    private val api: HostBackendApi,
) : UploadInitiator {
    override suspend fun initiate(request: UploadRequest): UploadSession {
        val resp = api.initiateDriveUpload(
            InitiateRequest(
                fileName = request.fileName,
                mimeType = request.mimeType,
                fileSizeBytes = request.fileSizeBytes,
                metadata = request.metadata,
            )
        )
        return UploadSession(
            uploadUrl = resp.uploadUrl,
            remoteFileId = resp.driveFileId,
            expiresAt = Instant.parse(resp.expiresAt),
        )
    }
}
```

See [`docs/BACKEND_CONTRACT.md`](docs/BACKEND_CONTRACT.md) for the exact shape
the backend must return.

### 3a. Wire with Hilt

```kotlin
@Module
@InstallIn(SingletonComponent::class)
abstract class HostDriveBindings {
    @Binds abstract fun bindInitiator(impl: HostUploadInitiator): UploadInitiator
}
```

That's it. `DriveUploader` is now injectable; `DriveUploaderModule` provides
the rest (config, OkHttp, Room, etc.).

### 3b. Wire without Hilt

```kotlin
val uploader = DriveUploaderFactory.create(
    context = applicationContext,
    initiator = MyInitiator(),
)
```

### 4. Upload a file

```kotlin
uploader.upload(
    localFile = File("/storage/.../IMG_001.jpg"),
    request = UploadRequest(
        fileName = "IMG_001.jpg",
        mimeType = "image/jpeg",
        fileSizeBytes = file.length(),
        metadata = mapOf("survey_id" to "12345"),
    ),
).collect { progress ->
    when (progress) {
        is UploadProgress.Transferring -> Timber.d("%.1f%%", progress.fraction * 100)
        is UploadProgress.Succeeded    -> Timber.i("done: %s", progress.webViewLink)
        is UploadProgress.Failed       -> Timber.w("failed retryable=%b", progress.isRetryable)
        is UploadProgress.Initiating   -> { /* show "preparing..." */ }
    }
}
```

### 5. (Optional) Use the bundled WorkManager worker

```kotlin
val request = OneTimeWorkRequestBuilder<DriveUploadWorker>()
    .setInputData(workDataOf(
        DriveUploadWorker.KEY_FILE_PATH to file.absolutePath,
        DriveUploadWorker.KEY_FILE_NAME to file.name,
        DriveUploadWorker.KEY_MIME_TYPE to "image/jpeg",
        DriveUploadWorker.KEY_FILE_SIZE to file.length(),
    ))
    .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
    .build()
WorkManager.getInstance(context).enqueue(request)
```

You can also run your own `CoroutineWorker` that injects `DriveUploader` and
calls `upload(...)` directly — both paths are first-class.

---

## When NOT to use this library

- **You need to call Drive directly from the device.** This library refuses to
  hold service-account credentials. If your app legitimately needs OAuth-based
  user-driven Drive access (e.g. signing in as the user and writing to *their*
  Drive), use the Google Drive REST client and Sign-In SDKs instead.
- **You need batched multi-file transfers.** This library uploads one file per
  call. A queue is the host's responsibility.
- **You need a different storage backend without a resumable PUT semantics.**
  S3 multipart works, Azure Block Blob works, Drive resumable uploads work.
  A backend with no resumable protocol does not.
- **You need progress with sub-chunk granularity.** Progress is emitted at
  chunk boundaries (default 1 MB). Tune `chunkSizeBytes` if you need finer
  feedback at the cost of more HTTP overhead.

---

## Threading and lifecycle notes

- `DriveUploader.upload` returns a **cold** `Flow`. No work happens until you
  collect.
- The flow runs on the collector's dispatcher. In practice, collect from
  `viewModelScope` for UI cases or inside a `CoroutineWorker` for background.
- **Single-flight per file path.** Two simultaneous `upload(...)` calls for the
  same `localFile` serialize internally so the local checkpoint never races.
  Different files upload concurrently.
- **Cancellation is safe.** Cancelling the collector cancels the in-flight HTTP
  request. The local checkpoint records the last server-acknowledged byte so a
  later call resumes from there.
- **Survives process death.** The checkpoint lives in a small dedicated Room
  database (`drive_uploader.db`) owned by this module. Your host DB is never
  touched.

---

## Configuration

Override defaults by providing a `DriveUploaderConfig`:

```kotlin
@Provides @Singleton
fun config() = DriveUploaderConfig(
    chunkSizeBytes = 4 * 1024 * 1024,    // 4 MiB chunks for fast networks
    maxAttemptsPerChunk = 8,
    initialBackoff = 500.milliseconds,
)
```

`chunkSizeBytes` must be a multiple of 256 KiB (Drive resumable protocol
requirement; the library enforces this in the constructor).

---

## What's owned by the library vs. the host

| Concern                                 | Library | Host |
|-----------------------------------------|:-------:|:----:|
| Bytes-on-the-wire to Drive              | Yes     |      |
| Chunking, resume, backoff               | Yes     |      |
| Local progress checkpoint (Room)        | Yes     |      |
| Session URL (remote)                    |         | Yes  |
| Service-account credential              |         | Yes  |
| Queue of "what to upload next"          |         | Yes  |
| Capture (camera/audio/video)            |         | Yes  |
| WorkManager scheduling policy           |         | Yes  |
| UI (progress dialogs, retry affordance) |         | Yes  |
