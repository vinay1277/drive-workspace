# Backend contract — `UploadInitiator` HTTP wire format

> **Audience**: host-application engineers writing an
> `UploadInitiator` against their own backend, and library
> contributors maintaining the reference server.
>
> **Companion to**: [ADR-0001](decisions/0001-backend-mediated-uploads.md)
> (no Drive credentials on the device),
> [ADR-0003](decisions/0003-session-prefetch-bank.md)
> (session prefetch bank, which adds the `count` parameter and the
> array response shape).

This document describes the HTTP shape the Phase 1 reference server
implements and that the tester's `BackendInitiator` parses. Hosts are
free to expose a different shape against their own backend; what
matters is that their `UploadInitiator` Kotlin implementation returns
`List<UploadSession>` of the right size from a single suspended call.

---

## Endpoint

```
POST /api/drive/initiate-upload[?count=N]
```

Authentication and routing headers are host-defined; the reference
server expects (and ignores) `X-Device-Token` and `Authorization:
Bearer …` on every request.

### Query parameters

| Param   | Type    | Default | Range            | Meaning                                     |
|---------|---------|---------|------------------|---------------------------------------------|
| `count` | integer | `1`     | `1..50`          | Number of resumable sessions to mint.       |

`count` is the prefetch-batch size (per ADR-0003). The library passes
`count=1` for the synchronous upload path and `count=N` for
`DriveUploader.prefetchSessions(N, ...)`. The cap (`50`) matches
`DriveUploader.MAX_PREFETCH_COUNT` on the library side; the server
returns `400` for values outside the range, non-integers, or absent
when expected.

### Request body

```json
{
  "file_name": "IMG_20260430.jpg",
  "mime_type": "image/jpeg",
  "file_size_bytes": 2340912,
  "kind_hint": "photo",
  "metadata": { "principal_id": "alice", "survey_id": "S-42" }
}
```

| Field              | Type            | Notes                                                      |
|--------------------|-----------------|------------------------------------------------------------|
| `file_name`        | string          | Display name. Reference server does not use it.            |
| `mime_type`        | string          | Drive uses this as the session's content type.             |
| `file_size_bytes`  | integer         | Used by the stub to track receipt; informational on real Drive — Drive trusts the chunk-PUT `Content-Range` headers. |
| `kind_hint`        | string \| null  | Optional. Bank fingerprint axis (ADR-0003). Server forwards it untouched. |
| `metadata`         | object          | Opaque host map. Routes the file to the right per-principal folder etc. Never interpreted by the library. |

For prefetch (`count > 1`) the request body is a *template* — the same
fields drive every session in the batch. Fields like `file_size_bytes`
end up bracketed by the library's prefetch-fingerprint anyway
(`<1MB`, `1-10MB`, `10-50MB`, `50MB+`); a 1-byte placeholder is fine
when the host doesn't know the real size yet.

### Response shape

**Always an array, even for `count=1`:**

```json
{
  "sessions": [
    {
      "upload_url":    "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=AB-…",
      "drive_file_id": "1abcDEF…",
      "expires_at":    "2026-05-07T12:34:56Z"
    },
    {
      "upload_url":    "https://…",
      "drive_file_id": "…",
      "expires_at":    "…"
    }
  ]
}
```

| Field           | Type                       | Notes                                                  |
|-----------------|----------------------------|--------------------------------------------------------|
| `upload_url`    | string                     | Opaque resumable PUT endpoint. The library never parses it. |
| `drive_file_id` | string                     | Echoed back to the host on `UploadProgress.Succeeded`. |
| `expires_at`    | RFC 3339 / ISO 8601 string | Informational. Bank prune respects this; chunk-PUT path detects real expiry via the 410/404 response and re-initiates. |

The array has exactly `count` entries on success. Short responses are
a contract violation; the reference server's `BackendInitiator` parser
treats them as an error.

### Status codes

| Code | When                                                                              |
|------|-----------------------------------------------------------------------------------|
| 200  | Sessions minted. Body is the array shape above.                                   |
| 400  | `count` out of range, non-integer, or otherwise malformed request.                |
| 401  | Authentication failed (host-defined; the reference server doesn't enforce auth).  |
| 5xx  | Backend error. The library treats `InitiateFailed` as retryable.                  |

---

## Reference implementation

Backend: [`backend/reference_server/app.py`](../backend/reference_server/app.py).
Library client: [`android/tester/src/main/kotlin/com/driveworkspace/tester/Initiators.kt`](../android/tester/src/main/kotlin/com/driveworkspace/tester/Initiators.kt)
(`BackendInitiator`).

The reference server is a Phase 1 stub — it mints fake `upload_url`s
and accepts chunk PUTs against itself. Phase 2 replaces the mint
implementation with real Drive API calls but the wire shape stays the
same.
