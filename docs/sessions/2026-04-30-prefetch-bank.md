# Session: 2026-04-30 — Apply ADR-0003 (session prefetch bank)

> **Library implementation session.** Add the session prefetch bank to
> `:core:drive` so a device with intermittent backend access can still
> upload to Drive against pre-minted resumable URLs. Pure client-side
> state-machine work; does not need real Drive or a working backend
> beyond the Phase 1 stub server.

## Goal

By end of session: the Android library exposes a new public method
`prefetchSessions(count, requestTemplate)` that mints N upload sessions
ahead of time and stores them locally. `DriveUploaderImpl.upload(...)`
draws from the bank first, falling through to a live `initiator.initiate`
call only when the bank is empty. The Phase 1 stub reference server is
extended to accept an optional `count` parameter and return an array of
sessions. End-to-end: tester app prefetches 5 sessions, kills network
to simulate "backend down," uploads succeeds anyway against the
already-minted URL.

## Required reading (before writing code)

- `docs/decisions/0003-session-prefetch-bank.md` — the spec
- `docs/architecture.md` §6 (backend offline tolerance) and §10 (repo layout)
- `docs/decisions/0010-library-dispatcher-discipline.md` (the prefetch
  call must also dispatch to IO per this ADR)
- `android/library/src/main/kotlin/com/driveworkspace/uploader/api/DriveUploader.kt`
- `android/library/src/main/kotlin/com/driveworkspace/uploader/internal/DriveUploaderImpl.kt`
- `android/library/src/main/kotlin/com/driveworkspace/uploader/internal/checkpoint/`
  (existing single-table Room database; this session adds a second table)
- `backend/reference_server/app.py` (the Phase 1 stub `initiate-upload`
  endpoint, adapted to accept `count`)

Do not read prior session transcripts.

## In scope

### Library

- New public API on `DriveUploader` interface:
  ```kotlin
  suspend fun prefetchSessions(
      count: Int,
      requestTemplate: UploadRequest,
  ): Int   // returns number of sessions actually banked
  ```
- New Room entity `BankedSessionEntity(uploadUrl, remoteFileId,
  expiresAt, mimeType, kindHint, fileSizeBracket, mintedAt)` and
  matching DAO. Schema version bumps to 2 with a migration.
- Bank lookup logic in `DriveUploaderImpl` — before calling
  `initiator.initiate`, attempt to draw a banked session matching the
  request's mime+kind+size-bracket fingerprint. Atomic claim (delete
  the row at draw time so concurrent uploads can't reuse it).
- Prune step on every prefetch + draw: drop sessions older than 5 days
  (per ADR-0003 — 2 days of safety margin against Drive's 7-day TTL).
- `prefetchSessions` itself dispatches the initiator call to IO per
  ADR-0010.
- Unit tests:
  - Prefetch banks N sessions, draw one, bank now N-1.
  - Concurrent draws never return the same session.
  - Stale sessions are pruned on next bank-touch.
  - Bank miss falls through to live initiate.
  - Sessions matching different fingerprints don't collide.

### Backend (reference server)

- `POST /api/drive/initiate-upload` accepts an optional `count` query
  param (default 1), returns `{"sessions": [...]}`. Behavior unchanged
  for `count=1` — but the response shape changes from a flat object to
  `{"sessions": [{...}]}`.
- The library's `BackendInitiator` (in tester) and the package's
  contract update to match.

### Tester app

- New "Prefetch 5 sessions" button next to "Upload" that calls
  `uploader.prefetchSessions(5, ...)`. Surfaces the returned count.
- Manual smoke step: prefetch 5; toggle airplane mode (or just kill the
  reference server); tap Upload; library should pull from bank and
  succeed against the still-valid stub URL.

### Docs

- `docs/architecture.md` §6 — update the diagram if needed (prefetch
  flow is already drawn, but confirm it matches what shipped).
- Update `BACKEND_CONTRACT.md` (if it exists; create if not — this is a
  good moment) describing the new `count` parameter and array response.

## Out of scope

- Background refill of the bank when it drops below a threshold. ADR-0003
  defers to "lazy refill" for now.
- Real Drive resumable URLs — Phase 2B. The Phase 1 stub server's
  fake URLs still work because they're in-memory state.
- Migrating existing checkpoint rows. v0.1.0 hasn't shipped; we can
  rebuild the DB.
- ADR-0011 (Shared Drives vs DWD) — separate session, doesn't gate this.

## Definition of done

- [ ] `prefetchSessions` is on the `DriveUploader` interface and works
      end-to-end against the reference server.
- [ ] `DriveUploaderImpl.upload` checks the bank before calling
      `initiator.initiate`. Verified by a unit test asserting the
      initiator is NOT called when a banked session matches.
- [ ] All existing tests pass (`./gradlew :library:test`,
      `./gradlew :tester:assembleDebug`, backend `pytest`).
- [ ] New tests added for: prefetch happy path, concurrent draw safety,
      stale-prune, bank miss fallthrough.
- [ ] Tester app has the "Prefetch 5 sessions" button and prints the
      banked count to the on-screen log.
- [ ] Reference server accepts `count` and returns the array shape.
- [ ] One commit per logical chunk (library API, room migration, impl,
      tester button, reference server). Final commit references this
      brief filename.

## Notes / open questions

1. **Fingerprint key** — what makes two sessions "match" for draw
   purposes? Recommend: `(mimeType, kindHint, fileSizeBracket)` where
   `fileSizeBracket` is one of `[< 1MB, 1-10MB, 10-50MB, 50MB+]`.
   This avoids minting one session per exact byte count (impossible)
   while staying close enough that Drive's session-size hint doesn't
   blow up the actual upload.
2. **Room migration vs. fall-through-DROP** — pre-v0.1.0 we can ship a
   destructive migration (drop and recreate). Recommend that for now;
   real migration discipline kicks in at v1.0.
3. **`count` upper bound** — server should cap at e.g. 50 to prevent
   accidental DoS via prefetch storm. Document it.

## Outcome

> Filled in at end of session.

(blank — to be completed)
