package com.driveworkspace.tester

import com.driveworkspace.uploader.api.UploadInitiator
import com.driveworkspace.uploader.api.UploadRequest
import com.driveworkspace.uploader.api.UploadSession
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant

/**
 * Direct mode: the operator pasted a pre-minted resumable session URL. We hand
 * it back wholesale so we can exercise the library against real Drive without
 * standing up a backend.
 *
 * Direct mode does not support batching; [initiate] rejects `count != 1`.
 */
class ManualInitiator(
    private val uploadUrl: String,
    private val remoteFileId: String,
) : UploadInitiator {
    override suspend fun initiate(request: UploadRequest, count: Int): List<UploadSession> {
        require(count == 1) {
            "ManualInitiator only supports count=1 (a single pasted URL); got count=$count. " +
                "Switch to Backend mode for prefetch."
        }
        return listOf(
            UploadSession(
                uploadUrl = uploadUrl,
                remoteFileId = remoteFileId,
                expiresAt = Instant.now().plusSeconds(3600),
            )
        )
    }
}

/**
 * Backend mode: hits POST <baseUrl>/api/drive/initiate-upload with the contract
 * defined in docs/BACKEND_CONTRACT.md.
 *
 * Per ADR-0003 the endpoint accepts an optional `?count=N` query param and
 * returns `{"sessions": [...]}` (always an array, even for count=1). Per
 * ADR-0010 the library invokes this on Dispatchers.IO so synchronous OkHttp
 * is safe here.
 */
class BackendInitiator(
    private val baseUrl: String,
    private val deviceToken: String,
    private val bearerToken: String,
    private val client: OkHttpClient = OkHttpClient(),
) : UploadInitiator {

    override suspend fun initiate(request: UploadRequest, count: Int): List<UploadSession> {
        require(count >= 1) { "count must be >= 1, was $count" }

        val body = JSONObject().apply {
            put("file_name", request.fileName)
            put("mime_type", request.mimeType)
            put("file_size_bytes", request.fileSizeBytes)
            put("metadata", JSONObject(request.metadata))
            request.kindHint?.let { put("kind_hint", it) }
        }.toString()

        val url = baseUrl.trimEnd('/') + "/api/drive/initiate-upload" +
            if (count == 1) "" else "?count=$count"

        val req = Request.Builder()
            .url(url)
            .header("X-Device-Token", deviceToken)
            .header("Authorization", "Bearer $bearerToken")
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()

        return client.newCall(req).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            check(resp.isSuccessful) { "initiate-upload HTTP ${resp.code}: $text" }
            val json = JSONObject(text)
            val arr: JSONArray = json.getJSONArray("sessions")
            check(arr.length() == count) {
                "initiate-upload returned ${arr.length()} sessions, expected $count"
            }
            buildList(arr.length()) {
                for (i in 0 until arr.length()) {
                    val s = arr.getJSONObject(i)
                    add(
                        UploadSession(
                            uploadUrl = s.getString("upload_url"),
                            remoteFileId = s.getString("drive_file_id"),
                            expiresAt = Instant.parse(s.getString("expires_at")),
                        )
                    )
                }
            }
        }
    }
}
