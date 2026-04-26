# `:tester` — Standalone harness for `:library`

A tiny, self-contained Android app that exercises the resumable Drive uploader
library in isolation. No SmartMeter business code. No Hilt. Single screen.
The point: prove the library is genuinely plug-and-play by dropping it into a
project that knows nothing about surveys.

## Install

```bash
./gradlew :tester:installDebug
```

It launches as **Drive Tester** on your device. Nothing else from the
SmartMeter app is involved.

## Two modes

### Direct mode — test against real Drive without a backend

Mint a resumable session yourself with a service-account access token:

```bash
ACCESS_TOKEN=$(gcloud auth print-access-token)

curl -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json; charset=UTF-8" \
  -H "X-Upload-Content-Type: image/jpeg" \
  -H "X-Upload-Content-Length: 4194304" \
  --data '{"name":"tester.jpg","parents":["YOUR_FOLDER_ID"]}' \
  -i \
  "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable"
```

Copy the `Location:` header from the response — that is the resumable upload
URL. Paste it into the **Resumable upload URL** field in the app, pick a file,
and tap **Upload**. The library streams the bytes directly to Drive.

### Backend mode — test the production path end-to-end

Once `POST /api/drive/initiate-upload` exists on the backend, switch to
**Backend** mode and supply:

- Backend base URL (e.g. `https://meternnj.com`)
- `X-Device-Token` value
- Bearer token (operator JWT)

The app's `BackendInitiator` calls the endpoint per
[`android/library/docs/BACKEND_CONTRACT.md`](../../android/library/docs/BACKEND_CONTRACT.md)
and hands the returned URL to the library.

## What this validates

- The library's public API is genuinely sufficient — this app uses *only*
  `DriveUploader`, `DriveUploaderFactory`, `UploadRequest`, `UploadProgress`,
  and the `UploadInitiator` interface. No `internal` types leaked.
- The non-Hilt construction path (`DriveUploaderFactory.create`) works. No
  Hilt is configured in this module.
- Resume semantics survive a process kill: upload a large file, force-stop the
  app mid-transfer, relaunch, pick the same file, hit Upload again — the
  library should resume from the last acknowledged chunk.
- Cancellation works: tap **Cancel** mid-flight and the in-flight HTTP request
  terminates cleanly.

## Logging

All progress events are mirrored to the on-screen log and to Logcat under tag
`DriveTester` / `DriveUpload`. Run `adb logcat -s DriveTester DriveUpload` to
follow along.
