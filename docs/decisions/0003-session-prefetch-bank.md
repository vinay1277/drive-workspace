# ADR-0003: Session prefetch bank for backend-offline tolerance

- **Status**: accepted
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

ADR-0001 puts the host backend on the upload-handshake path. This is a small
network call (~1 KB JSON each way) but it's still a hard dependency: if the
backend is unreachable, the device cannot mint a new resumable session and
cannot upload.

In real field use, the device may have cellular coverage strong enough to
reach Google's CDN-fronted Drive endpoints but not the host's specific
backend (backend down for maintenance, on-prem network partition, regional
ISP routing issue, etc.).

We want the device to keep uploading in that scenario without re-introducing
the security drawbacks of putting Drive credentials on the device.

## Decision

Add a **session prefetch bank** to the Android library.

- The library's checkpoint database gains a "session bank" table.
- New library API: `prefetchSessions(count: Int, requestTemplate: UploadRequest)`
  asks the backend to mint N sessions in advance and stashes them locally.
- New library behavior: when an upload starts, the library first tries to
  pull a session from the bank (matched by metadata fingerprint). Only if
  the bank is empty does it call `UploadInitiator.initiate()` synchronously.
- Backend endpoint accepts an optional `count` parameter (default 1) and
  returns an array of sessions.
- Stale sessions (older than ~5 days, leaving 2-day safety margin against
  Drive's 7-day TTL) are pruned on next bank-touch.

## Consequences

**Positive**:
- A device that prefetched 30 sessions during morning sync can upload 30
  files later in the day with the backend offline.
- No new credentials on the device. Bank entries are still single-file-bound,
  short-lived, opaque resumable URLs.
- Backend learns nothing new about the operational model — it just answers
  the same `initiate-upload` request with N items instead of 1.

**Negative**:
- Sessions in the bank that are never used are "stranded" — they consume a
  per-folder concurrent-resumable-upload count on Drive's side until they
  expire. Drive's documented limit is generous enough this isn't a real
  concern at typical fleet sizes.
- The library's local DB schema gets one more table. Migration cost: low
  (single Room version bump).
- The `requestTemplate` mechanism means prefetched sessions are bound to a
  shape (photo, audio, etc.) rather than a specific file. The library
  documents this; hosts can prefetch separate banks per kind if they want.

## Implementation notes

- Prefetch is opt-in. Hosts that don't call `prefetchSessions(...)` get the
  basic flow with no behavior change.
- Bank lookup is by metadata fingerprint (`mime_type` + `kind` + size
  bracket). On miss, fall through to live initiate.
- Sessions are claimed atomically; concurrent uploads from the same device
  cannot accidentally use the same session twice.
- Tester app gains a "prefetch 5 sessions" button for manual validation.

## Open question (closed 2026-04-30)

How aggressive should the bank refill be? Two options were considered:
- **Lazy**: refill only when explicitly asked.
- **Background**: when bank drops below threshold AND backend is reachable,
  refill in the background.

**Decided: lazy.** Host calls `prefetchSessions(...)` on its own
schedule; library does no autonomous network. Reconsider if hosts
request background-refill behavior. Shipped in commits `8a40f25` →
`07e908c` per `docs/sessions/2026-04-30-prefetch-bank.md`.

## Implementation status

Shipped in 2026-04-30 across five commits. Notable deltas from the
original spec:

- `UploadInitiator.initiate` signature changed to
  `suspend fun initiate(request, count: Int = 1): List<UploadSession>` —
  prefetch is a single backend round-trip, not N sequential ones. This
  is a pre-v0.1.0 breaking change to the host plug-point, accepted
  because the pre-v0.1.0 surface is explicitly unstable per ADR-0009.
- `UploadRequest.kindHint: String? = null` added as a typed slot for
  the fingerprint instead of magic key in `metadata`. Hosts that don't
  prefetch can ignore it.
- `MAX_PREFETCH_COUNT = 50` cap exposed as a public constant; the
  reference server enforces it server-side as well.
