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

ADR-0003 applied across library, tester, and reference server in five
commits as the brief specified.

**Library**

- `DriveUploader` interface gains
  `suspend fun prefetchSessions(count, requestTemplate): Int` plus a
  `MAX_PREFETCH_COUNT = 50` cap.
- `UploadInitiator.initiate` signature changes (pre-v0.1.0 break) to
  `suspend fun initiate(request, count: Int = 1): List<UploadSession>`
  so prefetch is a single backend round-trip rather than N sequential
  ones.
- `UploadRequest` gains `kindHint: String? = null` — typed slot for
  the prefetch fingerprint instead of a magic key in `metadata`.
- New Room schema (DB v2, destructive migration): `BankedSessionEntity`
  + `BankedSessionDao` with `@Transaction drawOne`. `BankStore`
  centralises the bank invariants — prune-on-touch (5-day TTL),
  fingerprint construction, kind-null sentinel.
- `DriveUploaderImpl` consults the bank before live initiate; bank hit
  bypasses `UploadInitiator.initiate` entirely (the headline DoD
  assertion). On `SessionExpired` the impl skips the bank for the
  retry to avoid drawing another likely-stale row.
- `DriveUploaderFactory` plumbs the new DAO; existing `DriveUploaderModule`
  (Hilt) needs no change because it goes through the factory.

**Tests** — all JVM-only via `FakeBankedSessionDao` (no Robolectric):

- prefetch banks N, draw shrinks to N-1
- 4×N concurrent draws against pool of N return exactly N unique rows
  (FakeBankedSessionDao serialises draws via Mutex to model Room's
  writer-thread serialisation)
- stale rows pruned on bank-touch (mutable `nowMs` clock)
- bank miss falls through to live initiate (initiator called once)
- bank hit and initiator NOT called
- different fingerprints don't collide (mime/kind/bracket axes)
- prefetch count > MAX coerced down

Existing `DriveUploaderDispatcherTest` updated for the new
`UploadInitiator` SAM signature and `DriveUploaderImpl`'s new `bank`
constructor parameter.

**Tester app** — "Prefetch 5 sessions" button added below the upload
row, only enabled in Backend mode. ViewModel builds a template
`UploadRequest(kindHint="tester-smoke", fileSizeBytes=1)`; the upload
path now uses the same `kindHint` so prefetched sessions actually
match. Manual smoke procedure (prefetch → kill backend → upload) is
documented inline next to the button.

**Reference server**

- `POST /api/drive/initiate-upload[?count=N]` — `count` defaults to 1,
  capped at `MAX_PREFETCH_COUNT = 50`. Validation: integer, in range,
  else 400 with `{"error": "..."}`.
- Response shape changes from a flat object to `{"sessions": [...]}`
  always — even for `count=1`.
- `tests/test_initiate_upload.py` covers the array shape for count=1
  and N, uniqueness across the batch, the cap edge, and the three
  rejection cases (out-of-range, zero, non-integer).

**Docs**

- New `docs/BACKEND_CONTRACT.md` — endpoint shape, `count` semantics,
  array response, status codes, links to ADR-0001 + ADR-0003 and to
  the reference impl + library client.

**Commits** (in order):
1. `feat(library): public API surface for prefetch bank` — `8a40f25`
2. `feat(library): Room schema for prefetch bank` — `72998bf`
3. `feat(library): wire prefetch bank into upload + prefetch paths` — `07e908c`
4. `feat(tester): Prefetch 5 sessions button + matching upload kindHint` — `4bcf74a`
5. (this commit) `feat(server): count param + array response shape;
   add BACKEND_CONTRACT.md` — references this brief filename.

**Verification status**: code-only this session. Build/test
verification (`./gradlew :library:test`, `:tester:assembleDebug`,
`pytest backend/`) is the next dev-box step. Any failure is a
follow-up; nothing in the design hinges on a result we couldn't get
from this environment.

**Out of scope (deferred)**:
- Background bank refill (ADR-0003 left this as "lazy" — confirmed).
- Phase 3 Android instrumentation test exercising the upload Flow
  collected on `Dispatchers.Main` — gap noted in ADR-0010 and still
  open.
