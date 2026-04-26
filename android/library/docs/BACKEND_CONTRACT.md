# Backend Contract — `:library`

This document specifies what the host app's backend MUST provide for the
`:library` Android library to function.

The Android library never holds Drive credentials. The backend is the trust
boundary: it owns the Drive service account, mints resumable upload sessions
on behalf of the device, and returns an opaque PUT URL to the device.

---

## 1. Endpoint

```
POST /api/drive/initiate-upload
```

### Request headers

| Header             | Required | Notes                                          |
|--------------------|:--------:|------------------------------------------------|
| `X-Device-Token`   | Yes      | Device-level auth, identical to other survey endpoints. |
| `Authorization`    | Yes      | `Bearer <surveyor-jwt>`. Operator-level auth.  |
| `Content-Type`     | Yes      | `application/json`                             |

### Request body

```json
{
  "file_name": "IMG_20260425_113042.jpg",
  "mime_type": "image/jpeg",
  "file_size_bytes": 4194304,
  "metadata": {
    "survey_id": "12345",
    "ivrs_no": "N1822001449",
    "capture_kind": "meter_photo"
  }
}
```

- `file_name`, `mime_type`: strings, both required and non-empty.
- `file_size_bytes`: integer, > 0. Used to set the resumable session size on
  Drive's side and to guard against malformed clients.
- `metadata`: free-form `string -> string` map. The library never inspects it;
  whatever the host's `UploadInitiator` puts in is what the backend gets.
  Recommended keys: `survey_id`, business identifiers, `capture_kind`.

### Response — 200 OK

```json
{
  "upload_url": "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=AEnB...",
  "drive_file_id": "1AbCdEfGhIjKlMnOpQ",
  "expires_at": "2026-04-25T18:00:00Z"
}
```

- `upload_url`: the resumable session URL Drive returns from
  `POST /upload/drive/v3/files?uploadType=resumable`. The Android library
  treats this as an opaque endpoint and PUTs chunks to it directly.
- `drive_file_id`: the `id` from Drive's response (or whatever stable ID the
  backend assigns). The library echoes it back on `UploadProgress.Succeeded`.
- `expires_at`: ISO-8601 UTC. Informational only — the library detects actual
  expiry from Drive's `410 Gone` / `404` and re-calls this endpoint.

### Error responses

The library treats any non-2xx as a non-retryable initiate failure surfaced as
`UploadError.InitiateFailed`. The backend should follow standard conventions:

| Status | When                                      |
|--------|-------------------------------------------|
| 401    | Missing/invalid device token or JWT       |
| 403    | Operator not allowed to upload            |
| 422    | Validation failed (`file_size_bytes <= 0` etc.) |
| 429    | Rate-limited; the library does not auto-retry initiate (host's call) |
| 5xx    | Backend or Drive failure                  |

---

## 2. Backend responsibilities

The backend MUST:

1. **Authenticate.** Validate `X-Device-Token` and the operator JWT.
2. **Authorize.** Confirm this device/operator may upload to the target
   Drive folder for the supplied `metadata`. The mapping from metadata to
   Drive folder is host-app business logic.
3. **Mint a resumable session against Drive.**
   - Use the service-account credential (server-side only — never push it to
     the device).
   - `POST https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable`
   - Body: Drive metadata (`name`, `mimeType`, `parents`, etc.), plus the
     `X-Upload-Content-Length` header set to `file_size_bytes`.
   - Drive responds with a `Location:` header — that's the `upload_url`.
4. **Pre-register the file row in Drive.** Drive's resumable session creation
   already does this and returns a `file_id` you can use for `drive_file_id`.
5. **Persist a local audit row** linking `drive_file_id` ↔ device ↔ operator ↔
   `metadata` so that surveys later submitted with that `drive_file_id` can be
   correlated.
6. **Return promptly.** Target p99 < 2 s. The device is on cellular and
   blocking the surveyor on a slow initiate is bad UX.

The backend MUST NOT:

- Stream file bytes through itself. The device PUTs directly to Drive's
  `upload_url`. The backend's only job is the auth + minting handshake.
- Re-use the same `upload_url` across calls. Each `initiate` produces a fresh
  session. Idempotency is on the library side (it caches the session locally
  via the checkpoint table; if the host's `UploadInitiator` is called twice in
  rapid succession the library is happy to use either URL).

---

## 3. Idempotency notes for the backend

Because the library re-calls this endpoint when a session expires, the backend
will see multiple `initiate` calls per logical file. That's expected. The
backend should:

- Record each `drive_file_id` it mints, with a status of `pending`.
- When the survey is finally submitted referencing some `drive_file_id`, mark
  that row `committed` and any *other* rows minted for the same logical file
  but never used as `orphaned`.
- Periodically (cron or admin job) reconcile `pending` rows older than 24 h
  with Drive: if Drive doesn't have completed bytes, delete the file from
  Drive and mark the row `abandoned`.

This keeps a multi-attempt upload from leaving zombie partial files in Drive.

---

## 4. Worked example

Library wants to upload a 12 MiB photo:

```
Device → POST /api/drive/initiate-upload
        body { file_name, mime_type, file_size_bytes: 12582912, metadata }
Backend → Drive  POST /upload/drive/v3/files?uploadType=resumable
                 body { name, mimeType, parents: ["folderID"] }
                 hdr  X-Upload-Content-Length: 12582912
Drive   → 200 with Location: https://www.googleapis.com/upload/drive/v3/...&upload_id=ABC
Backend → Device 200 { upload_url: "...", drive_file_id: "1Xy...", expires_at: "..." }
Device  → PUT upload_url with Content-Range: bytes 0-1048575/12582912
        (repeats with 1 MiB chunks; receives 308 between chunks)
Drive   → 200 final response with file metadata
```

That's the full handshake. Everything between the first `POST /api/drive/initiate-upload`
and the final `200` from Drive is owned by the library — the backend only sees
the initial mint.

---

## 5. Security checklist

- [ ] Service-account JSON key is server-side only; never in the APK or any
      device-readable storage.
- [ ] Device tokens and operator JWTs are validated on every call to
      `/api/drive/initiate-upload`. No "for testing" bypass.
- [ ] Drive folder resolution from `metadata` rejects unknown metadata keys
      rather than defaulting to a shared folder.
- [ ] Audit log records every minted `drive_file_id` with the requesting
      device + operator + timestamp.
- [ ] `upload_url` is treated as a secret in transit (HTTPS-only — already
      true since Drive only accepts HTTPS).
