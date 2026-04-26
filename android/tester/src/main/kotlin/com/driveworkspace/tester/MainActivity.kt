package com.driveworkspace.tester

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

class MainActivity : ComponentActivity() {
    private val vm: TesterViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme { TesterScreen(vm) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TesterScreen(vm: TesterViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    val pickFile = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let(vm::onFilePicked)
    }

    Scaffold(topBar = { TopAppBar(title = { Text("Drive Uploader Tester") }) }) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // Mode toggle
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Text("Mode:", modifier = Modifier.padding(end = 8.dp))
                FilterChip(
                    selected = state.mode == Mode.DIRECT,
                    onClick = { vm.setMode(Mode.DIRECT) },
                    label = { Text("Direct") },
                )
                Spacer(Modifier.width(8.dp))
                FilterChip(
                    selected = state.mode == Mode.BACKEND,
                    onClick = { vm.setMode(Mode.BACKEND) },
                    label = { Text("Backend") },
                )
            }

            HorizontalDivider()

            when (state.mode) {
                Mode.DIRECT -> {
                    OutlinedTextField(
                        value = state.uploadUrl,
                        onValueChange = vm::setUploadUrl,
                        label = { Text("Resumable upload URL") },
                        singleLine = false,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = state.remoteFileId,
                        onValueChange = vm::setRemoteFileId,
                        label = { Text("Remote file id (informational)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Text(
                        "Mint a session with: curl -X POST -H 'Authorization: Bearer <token>' " +
                            "-H 'X-Upload-Content-Length: <size>' " +
                            "'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable' " +
                            "-d '{\"name\":\"test.bin\"}' -i",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Mode.BACKEND -> {
                    OutlinedTextField(
                        value = state.backendUrl,
                        onValueChange = vm::setBackendUrl,
                        label = { Text("Backend base URL (e.g. https://meternnj.com)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = state.deviceToken,
                        onValueChange = vm::setDeviceToken,
                        label = { Text("X-Device-Token") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = state.bearerToken,
                        onValueChange = vm::setBearerToken,
                        label = { Text("Bearer token") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

            OutlinedTextField(
                value = state.mimeType,
                onValueChange = vm::setMimeType,
                label = { Text("MIME type") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii),
                modifier = Modifier.fillMaxWidth(),
            )

            HorizontalDivider()

            // File picker + upload controls
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = { pickFile.launch("*/*") },
                    enabled = !state.isUploading,
                ) { Text("Pick file") }

                Button(
                    onClick = vm::startUpload,
                    enabled = !state.isUploading && state.pickedFile != null,
                ) { Text("Upload") }

                OutlinedButton(
                    onClick = vm::cancelUpload,
                    enabled = state.isUploading,
                ) { Text("Cancel") }
            }

            state.pickedFile?.let { f ->
                Text("File: ${f.displayName}  (${f.sizeBytes} bytes)",
                    style = MaterialTheme.typography.bodySmall)
            }

            // Progress
            if (state.bytesTotal > 0) {
                LinearProgressIndicator(
                    progress = { state.progress.coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth(),
                )
                Text("${state.bytesUploaded} / ${state.bytesTotal}  (${(state.progress * 100).toInt()}%)",
                    style = MaterialTheme.typography.bodySmall)
            }

            state.terminal?.let { Text(it, style = MaterialTheme.typography.titleMedium) }

            HorizontalDivider()
            Text("Log", style = MaterialTheme.typography.titleSmall)
            Column {
                state.log.takeLast(50).forEach { line ->
                    Text(line, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}
