# ADR-0001: Backend-mediated uploads; no Drive credentials on the device

- **Status**: accepted
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

Field-survey devices need to upload media (photos, audio, video, often 30+ MB)
to org-owned Google Drive. Three architectural options exist:

1. **SA key on the device.** Bundle a service-account JSON in the APK or
   download it on first launch.
2. **Per-user OAuth on the device.** Each surveyor signs in with their Google
   account; device holds an OAuth refresh token; uploads use that token.
3. **Backend-mediated.** Backend holds the SA credential. Device asks backend
   to mint a resumable upload URL; device PUTs bytes directly to that URL.

## Decision

We choose option 3: **backend-mediated uploads.** The Android library holds
no Drive credential of any kind. The backend's service-account credential
never leaves the server. The device's only Drive interaction is PUT-ing bytes
to opaque, short-lived, single-file resumable session URLs minted by the
backend.

## Consequences

**Positive**:
- Device compromise leaks at most: one device's host-app token, one operator's
  JWT, and any in-flight resumable URLs (single-file-bound, ~7-day TTL).
- Credential rotation is server-only.
- Audit is centralized: every upload starts with a backend call, recorded in
  the host's audit log alongside `(device_id, principal_id, drive_file_id)`.
- Quota and abuse control sit on the backend, before any Drive API call.
- No per-user Workspace seat costs (option 2 cost: ~$6/seat/month × N
  surveyors).

**Negative**:
- The backend is on the upload-handshake path. If the backend is unreachable,
  the device cannot mint new sessions. Mitigated by the **session prefetch
  bank** (ADR-0003), which lets a device pre-mint sessions while the backend
  is reachable and draw from the bank when it isn't.
- Adds one HTTP round-trip per file (the initiate call). Trivial relative to
  multi-MB uploads.

**Rejected alternatives**:
- *SA key on the device*: trivially exfiltrated from a rooted phone. The
  encryption-at-rest argument doesn't hold — the decryption key would also
  ship with the APK.
- *Per-user OAuth*: works but costs Workspace seats, makes audit
  multi-principal, and reintroduces a long-lived Drive credential on the
  device. The "credentials never on device" property is more valuable than
  the offline-tolerance property; we recover the latter via prefetch bank.

## Implementation notes

- The Android library defines a `UploadInitiator` interface; the host app
  implements it by calling whatever endpoint the host's backend exposes.
- The library treats the returned `uploadUrl` as opaque — never parses it,
  never modifies it, never adds auth headers to PUTs against it.
- See `architecture.md` §3 for the trust-boundary diagram.
