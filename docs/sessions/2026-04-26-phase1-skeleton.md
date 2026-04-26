# Session: 2026-04-26 — Phase 1 skeleton

> **First post-bootstrap session.** Stand up the runnable structure: empty
> Python package, empty Flask reference server, ported Android library +
> tester, docker-compose. Nothing real yet — everything is mocked.

## Goal

By end of session: `docker compose up` boots a Flask server with a `/health`
endpoint and a stub `POST /api/drive/initiate-upload` returning a fake
session. The Android tester app installs cleanly and successfully completes
a fake upload against the reference server's stub endpoints.

This proves the structure holds before we start writing real Drive logic in
Phase 2.

## Required reading (before writing code)

- `docs/architecture.md` (the whole thing — it's only ~5 pages)
- `docs/decisions/0004-modular-package-with-host-plugins.md`
- `docs/decisions/0005-monorepo-three-subtrees.md`
- `docs/decisions/0006-stack-choices.md`
- `docs/plan.md` § "Phase 1 — Skeleton"

Existing source to port (do not re-derive):
- `D:\Android\Claude\.claude\worktrees\ecstatic-pasteur-d55fa2\core\drive\` →
  becomes `android/library/`. Strip SmartMeter package paths
  (`com.jpss.smartmeter.core.drive` → `com.driveworkspace.uploader` or
  similar — propose during the session).
- `D:\Android\Claude\.claude\worktrees\ecstatic-pasteur-d55fa2\sample\drive-tester\` →
  becomes `android/tester/`. Same package rename.

## In scope

### Backend

- `backend/drive_workspace/__init__.py` — empty for now, just makes the
  package importable.
- `backend/drive_workspace/workspace.py` — `class DriveWorkspace`
  constructor signature only; methods raise `NotImplementedError`.
- `backend/drive_workspace/{folders,uploads,logs,reconcile}.py` — stub
  classes mirroring the architecture sketch; all methods raise.
- `backend/drive_workspace/stores/protocol.py` — `PrincipalStore` Protocol.
- `backend/drive_workspace/stores/sqlalchemy.py` — empty file (Phase 2).
- `backend/drive_workspace/adapters/flask.py` — empty file (Phase 2).
- `backend/reference_server/app.py` — minimal Flask app:
  - `GET /health` → `{"status": "ok"}`
  - `POST /api/drive/initiate-upload` → returns hard-coded fake session:
    ```json
    {
      "upload_url": "http://localhost:8080/_stub/upload/<random_id>",
      "drive_file_id": "fake-<random_id>",
      "expires_at": "2099-01-01T00:00:00Z"
    }
    ```
  - `PUT /_stub/upload/<id>` — accepts the chunked PUT, returns 308 with
    `Range: bytes=0-<received>` until the full size is received, then 200
    with `{"id": "...", "webViewLink": null}`. This makes the tester
    end-to-end without involving Drive.
- `backend/Dockerfile` — Python 3.11-slim, install package, run
  `flask --app reference_server.app run --host=0.0.0.0 --port=8080`.
- `backend/README.md` — how to run locally, how to run tests.

### Android

- Move `core/drive/` → `android/library/` with package rename.
- Move `sample/drive-tester/` → `android/tester/` with package rename.
- `android/gradle/libs.versions.toml` — copy from
  `D:\Android\Claude\.claude\worktrees\ecstatic-pasteur-d55fa2\gradle\libs.versions.toml`,
  trim to what's actually used (no Maps/Firebase/etc.).
- `android/build.gradle.kts` (root) — minimal plugin declarations.
- `android/library/build.gradle.kts` — verify still builds after rename.
- `android/tester/build.gradle.kts` — same.
- Tester default backend URL: `http://10.0.2.2:8080` (emulator), document
  `adb reverse tcp:8080 tcp:8080` for physical device.

### Repo root

- `docker-compose.yml`:
  - `postgres:16` (volume-backed, exposed for psql convenience)
  - `reference_server` built from `backend/Dockerfile`, port 8080,
    `DATABASE_URL` env pointing at postgres
- `.github/workflows/backend-ci.yml`: `pip install -e backend[dev] && ruff check && mypy --strict backend/drive_workspace && pytest backend/`. Don't fail on no-tests-collected — Phase 1 has no real tests yet.

## Out of scope

- Any real Drive API call. The reference server's stub endpoints simulate
  Drive end-to-end for Phase 1.
- Real `PrincipalStore` schema or migrations. Stubs only.
- Real Sheets API logic. Stub only.
- Reconciliation logic. Empty class only.
- Session prefetch bank wiring. Phase 2.
- Android CI workflow. Phase 3.
- Integration tests. Phase 3.
- Sphinx docs build. Phase 3.

## Definition of done

- [ ] `docker compose up` from repo root brings up postgres + reference_server with no errors.
- [ ] `curl http://localhost:8080/health` returns `{"status": "ok"}`.
- [ ] `curl -X POST http://localhost:8080/api/drive/initiate-upload -H 'Content-Type: application/json' -d '{"file_name":"x","mime_type":"image/jpeg","file_size_bytes":1000}'` returns a JSON session object.
- [ ] `cd android && ./gradlew :tester:assembleDebug` succeeds.
- [ ] `./gradlew :tester:installDebug` on a connected emulator/device installs the app.
- [ ] In the tester app: pick any small file → tap Upload → see Succeeded with the stub `drive_file_id`.
- [ ] `cd backend && pip install -e .[dev] && ruff check . && mypy --strict drive_workspace/` is clean (no real code yet, so this is mostly verifying configuration).
- [ ] `docs/plan.md` Phase 1 tasks marked complete; `docs/sessions/2026-04-26-phase1-skeleton.md` ends with a "Outcome" section summarizing what shipped.
- [ ] One commit per logical chunk (backend skeleton, Android port, docker-compose, CI). Final commit message references this session brief.

## Notes / open questions

1. **Android package rename target** — propose 2-3 candidates (e.g.
   `com.driveworkspace.uploader`, `org.driveworkspace.uploader`,
   `com.example.driveworkspace`). Pick the boring one.
2. **Reference server port** — 8080 default; surface if a different choice
   is better for the dev's setup.
3. **Postgres credentials** — for local dev only, use `dev`/`dev`/`dev`. The
   reference server `DATABASE_URL` reads from env, so this is just the
   docker-compose default.
4. **Should `pyproject.toml` move to repo root** so `pip install -e backend`
   becomes `pip install -e .` from root? Recommendation: keep it under
   `backend/` so the backend tree is self-contained — matters for the day
   we move the package to its own repo.

## Outcome

Phase 1 skeleton landed in four logical commits:

1. **Backend skeleton** — `drive_workspace/` package with stub `DriveWorkspace`
   facade and sub-managers (`FolderManager`, `UploadSessionMint`,
   `SpreadsheetLogger`, `ReconciliationRunner`); `PrincipalStore` and
   `LogSchema` Protocols; empty `stores/sqlalchemy.py` and `adapters/flask.py`
   placeholders. Reference Flask server with `GET /health`, `POST
   /api/drive/initiate-upload`, and a `PUT /_stub/upload/<id>` endpoint that
   fakes Drive's resumable behavior end-to-end (308 between chunks, 200 with
   metadata at completion). `Dockerfile` (python:3.11-slim) and
   `backend/README.md`. `ruff` and `mypy --strict` were run locally and are
   clean.
2. **Android port** — `core/drive/` → `android/library/` and
   `sample/drive-tester/` → `android/tester/`, with package rename
   `com.jpss.smartmeter.core.drive` → `com.driveworkspace.uploader` and
   `com.jpss.smartmeter.sample.drivetester` → `com.driveworkspace.tester`.
   `android/gradle/libs.versions.toml` trimmed to only what library + tester
   actually reference (dropped Maps/Firebase/navigation/CameraX/Coil/
   Accompanist/exif/location/datastore/security). Tester defaults
   `backendUrl` to `http://10.0.2.2:8080` with stub device/bearer tokens;
   manifest enables cleartext for the dev server. Gradle wrapper +
   `gradle.properties` (sans `MAPS_API_KEY`) copied from V2.
3. **docker-compose.yml** — postgres:16 (`dev`/`dev`/`dev`) with healthcheck
   gate + `reference_server` service.
4. **CI** — `.github/workflows/backend-ci.yml` runs ruff, mypy --strict, and
   pytest (treats exit code 5 — no tests collected — as success until
   Phase 3).

### Decisions taken inline (within scope of the open questions)

- **Package rename target**: `com.driveworkspace.uploader` (library),
  `com.driveworkspace.tester` (tester app). Boring, no fake-org or
  `.example` prefix; reflects that this is proprietary in-house plumbing
  (architecture §12).
- **Postgres dev creds**: `dev`/`dev`/`dev` per the brief.
- **Port**: 8080.
- **`pyproject.toml` location**: kept under `backend/` per the brief's
  recommendation.

### Verified

- `python -m ruff check .` and `python -m mypy --strict drive_workspace/`
  in `backend/` are both clean.

### Not verified by this session (require dev environment)

- `docker compose up` end-to-end (no Docker invoked; compose file is
  written but not executed).
- `./gradlew :tester:assembleDebug` / `:tester:installDebug` (no Android
  SDK / device available in this session).
- The full tap-Upload-see-Succeeded loop on a real emulator.

These are the runtime checks in the Definition of Done; the next person to
boot this on a dev box should walk through them. If anything fails, log the
fix in a follow-up session brief rather than amending this one.

### Notes for the next session

- A real-looking `MAPS_API_KEY` was present in the source SmartMeter V2
  worktree's `gradle.properties`. It was stripped before being copied here,
  but it remains in the SmartMeter repo and is worth rotating out-of-band.
- Phase 2 entry: ADR-0006 already calls out `mypy --strict` from day one;
  the empty test directories exist so Phase 3 can drop tests in place.
- The reference server's stub PUT keeps per-upload byte-receipt state in
  an in-memory dict guarded by a lock. Single-worker only; fine for Phase 1
  but obviously goes away in Phase 2 when real Drive resumable URLs take
  over.
