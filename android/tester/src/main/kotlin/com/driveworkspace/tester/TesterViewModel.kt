package com.driveworkspace.tester

import android.app.Application
import android.content.ContentResolver
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.driveworkspace.uploader.DriveUploaderFactory
import com.driveworkspace.uploader.api.UploadInitiator
import com.driveworkspace.uploader.api.UploadProgress
import com.driveworkspace.uploader.api.UploadRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.io.File

enum class Mode { DIRECT, BACKEND }

data class TesterUiState(
    val mode: Mode = Mode.BACKEND,
    val pickedFile: PickedFile? = null,

    // Direct-mode inputs
    val uploadUrl: String = "",
    val remoteFileId: String = "manual-test",

    // Backend-mode inputs — defaults point at the reference server running on
    // the host (10.0.2.2 is the emulator alias for the host's localhost). For
    // a physical device, run `adb reverse tcp:8080 tcp:8080` and use the same
    // URL, or replace with the LAN IP of the host.
    val backendUrl: String = "http://10.0.2.2:8080",
    val deviceToken: String = "stub-device",
    val bearerToken: String = "stub-bearer",

    val mimeType: String = "application/octet-stream",
    val isUploading: Boolean = false,
    val isPrefetching: Boolean = false,
    val progress: Float = 0f,
    val bytesUploaded: Long = 0,
    val bytesTotal: Long = 0,
    val log: List<String> = emptyList(),
    val terminal: String? = null,
)

data class PickedFile(
    val displayName: String,
    val sizeBytes: Long,
    val cacheFile: File,
    val mimeType: String,
)

class TesterViewModel(app: Application) : AndroidViewModel(app) {

    private val _state = MutableStateFlow(TesterUiState())
    val state: StateFlow<TesterUiState> = _state.asStateFlow()

    private var uploadJob: Job? = null

    fun setMode(mode: Mode) = _state.update { it.copy(mode = mode) }
    fun setUploadUrl(v: String) = _state.update { it.copy(uploadUrl = v) }
    fun setRemoteFileId(v: String) = _state.update { it.copy(remoteFileId = v) }
    fun setBackendUrl(v: String) = _state.update { it.copy(backendUrl = v) }
    fun setDeviceToken(v: String) = _state.update { it.copy(deviceToken = v) }
    fun setBearerToken(v: String) = _state.update { it.copy(bearerToken = v) }
    fun setMimeType(v: String) = _state.update { it.copy(mimeType = v) }

    fun onFilePicked(uri: Uri) {
        viewModelScope.launch {
            val picked = withContext(Dispatchers.IO) { copyToCache(uri) }
            if (picked == null) {
                appendLog("Could not read picked file")
                return@launch
            }
            _state.update {
                it.copy(
                    pickedFile = picked,
                    mimeType = picked.mimeType,
                    bytesTotal = picked.sizeBytes,
                    bytesUploaded = 0,
                    progress = 0f,
                    terminal = null,
                )
            }
            appendLog("Picked: ${picked.displayName} (${picked.sizeBytes} bytes)")
        }
    }

    fun startUpload() {
        val s = _state.value
        val file = s.pickedFile?.cacheFile ?: run {
            appendLog("Pick a file first."); return
        }
        val initiator = buildInitiator(s) ?: return

        uploadJob?.cancel()
        _state.update { it.copy(isUploading = true, progress = 0f, terminal = null) }
        appendLog("Starting upload mode=${s.mode} file=${file.name}")

        uploadJob = viewModelScope.launch {
            val uploader = DriveUploaderFactory.create(getApplication(), initiator)
            val req = UploadRequest(
                fileName = s.pickedFile.displayName,
                mimeType = s.mimeType,
                fileSizeBytes = file.length(),
                kindHint = "tester-smoke",
                metadata = mapOf("source" to "drive-tester"),
            )
            uploader.upload(file, req).collect { event ->
                when (event) {
                    is UploadProgress.Initiating -> appendLog("→ initiating (attempt ${event.attempt})")
                    is UploadProgress.Transferring -> _state.update {
                        it.copy(
                            bytesUploaded = event.bytesUploaded,
                            bytesTotal = event.bytesTotal,
                            progress = event.fraction,
                        )
                    }
                    is UploadProgress.Succeeded -> {
                        appendLog("✓ succeeded id=${event.remoteFileId}")
                        event.webViewLink?.let { appendLog("  link: $it") }
                        _state.update { it.copy(isUploading = false, terminal = "Succeeded", progress = 1f) }
                    }
                    is UploadProgress.Failed -> {
                        appendLog("✗ failed retryable=${event.isRetryable} ${event.error::class.simpleName}: ${event.error.message}")
                        Timber.tag(TAG).w(event.error, "upload failed")
                        _state.update { it.copy(isUploading = false, terminal = "Failed: ${event.error::class.simpleName}") }
                    }
                }
            }
        }
    }

    fun cancelUpload() {
        uploadJob?.cancel()
        _state.update { it.copy(isUploading = false) }
        appendLog("Cancelled.")
    }

    /**
     * ADR-0003 manual smoke test. Mints [count] sessions ahead of time and
     * stashes them in the library's local bank. Only useful in BACKEND
     * mode — DIRECT mode's [ManualInitiator] rejects count != 1.
     *
     * The template UploadRequest uses the current MIME plus a 1-byte
     * placeholder size; the resulting fingerprint covers the `<1MB`
     * bracket which matches typical tester workflows (small synthesised
     * payloads). Real-world fleets pick the bracket at prefetch time
     * based on expected workload.
     */
    fun prefetchSessions(count: Int) {
        val s = _state.value
        if (s.mode != Mode.BACKEND) {
            appendLog("Prefetch only works in Backend mode (ManualInitiator is single-URL).")
            return
        }
        val initiator = buildInitiator(s) ?: return
        _state.update { it.copy(isPrefetching = true) }
        appendLog("→ prefetching $count sessions…")
        viewModelScope.launch {
            val uploader = DriveUploaderFactory.create(getApplication(), initiator)
            val template = UploadRequest(
                fileName = "prefetch-template",
                mimeType = s.mimeType,
                fileSizeBytes = 1L,
                kindHint = "tester-smoke",
                metadata = mapOf("source" to "drive-tester-prefetch"),
            )
            val banked = try {
                uploader.prefetchSessions(count, template)
            } catch (t: Throwable) {
                Timber.tag(TAG).w(t, "prefetch failed")
                appendLog("✗ prefetch threw: ${t.message}")
                _state.update { it.copy(isPrefetching = false) }
                return@launch
            }
            appendLog("✓ banked $banked / $count sessions")
            _state.update { it.copy(isPrefetching = false) }
        }
    }

    private fun buildInitiator(s: TesterUiState): UploadInitiator? = when (s.mode) {
        Mode.DIRECT -> {
            if (s.uploadUrl.isBlank()) {
                appendLog("Paste a resumable upload URL first."); null
            } else ManualInitiator(s.uploadUrl, s.remoteFileId.ifBlank { "manual-test" })
        }
        Mode.BACKEND -> {
            if (s.backendUrl.isBlank() || s.deviceToken.isBlank() || s.bearerToken.isBlank()) {
                appendLog("Backend URL, device token, and bearer token are required."); null
            } else BackendInitiator(s.backendUrl, s.deviceToken, s.bearerToken)
        }
    }

    private fun appendLog(line: String) {
        Timber.tag(TAG).i(line)
        _state.update { it.copy(log = (it.log + line).takeLast(MAX_LOG_LINES)) }
    }

    private fun copyToCache(uri: Uri): PickedFile? {
        val app = getApplication<Application>()
        val cr: ContentResolver = app.contentResolver
        val name = queryDisplayName(uri) ?: "picked-${System.currentTimeMillis()}"
        val mime = cr.getType(uri) ?: "application/octet-stream"
        val target = File(app.cacheDir, "drive-tester/$name").apply { parentFile?.mkdirs() }
        cr.openInputStream(uri)?.use { input ->
            target.outputStream().use { output -> input.copyTo(output) }
        } ?: return null
        return PickedFile(name, target.length(), target, mime)
    }

    private fun queryDisplayName(uri: Uri): String? {
        val cr = getApplication<Application>().contentResolver
        cr.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst()) return c.getString(0)
        }
        return null
    }

    private companion object {
        const val TAG = "DriveTester"
        const val MAX_LOG_LINES = 200
    }
}
