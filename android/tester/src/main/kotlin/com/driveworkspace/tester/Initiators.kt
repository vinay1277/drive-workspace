package com.driveworkspace.tester

import com.driveworkspace.uploader.api.UploadInitiator
import com.driveworkspace.uploader.api.UploadRequest
import com.driveworkspace.uploader.api.UploadSession
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.time.Instant

/**
 * Direct mode: the operator pasted a pre-minted resumable session URL. We hand
 * it back wholesale so we can exercise the library against real Drive without
 * standing up a backend.
 */
class ManualInitiator(
    private val uploadUrl: String,
    private val remoteFileId: String,
) : UploadInitiator {
    override suspend fun initiate(request: UploadRequest): UploadSession =
        UploadSession(
            uploadUrl = uploadUrl,
            remoteFileId = remoteFileId,
            expiresAt = Instant.now().plusSeconds(3600),
        )
}

/**
 * Backend mode: hits POST <baseUrl>/api/drive/initiate-upload with the contract
 * defined in core/drive/docs/BACKEND_CONTRACT.md.
 */
class BackendInitiator(
    private val baseUrl: String,
    private val deviceToken: String,
    private val bearerToken: String,
    private val client: OkHttpClient = OkHttpClient(),
) : UploadInitiator {

    // Synchronous OkHttp is safe here: per ADR-0010 the library invokes
    // UploadInitiator.initiate() on Dispatchers.IO, so this body already runs
    // off the main thread regardless of the flow collector's dispatcher.
    override suspend fun initiate(request: UploadRequest): UploadSession {
        val body = JSONObject().apply {
            put("file_name", request.fileName)
            put("mime_type", request.mimeType)
            put("file_size_bytes", request.fileSizeBytes)
            put("metadata", JSONObject(request.metadata))
        }.toString()

        val req = Request.Builder()
            .url(baseUrl.trimEnd('/') + "/api/drive/initiate-upload")
            .header("X-Device-Token", deviceToken)
            .header("Authorization", "Bearer $bearerToken")
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()

        return client.newCall(req).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            check(resp.isSuccessful) { "initiate-upload HTTP ${resp.code}: $text" }
            val json = JSONObject(text)
            UploadSession(
                uploadUrl = json.getString("upload_url"),
                remoteFileId = json.getString("drive_file_id"),
                expiresAt = Instant.parse(json.getString("expires_at")),
            )
        }
    }
}
