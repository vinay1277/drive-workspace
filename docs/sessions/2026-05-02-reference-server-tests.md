# Session: 2026-05-02 — Reference server tests

> **Test-only session.** The Phase 1 reference Flask server has
> non-trivial state-machine logic (Content-Range parsing, 308/200
> resumable protocol) and zero tests. This session adds pytest coverage
> using `flask.test_client`. No production code changes.

## Goal

By end of session: `pytest backend/reference_server/tests/` runs green
with ≥90% line coverage on `reference_server/app.py`. Tests cover
`/health`, `POST /api/drive/initiate-upload`, and the `PUT
/_stub/upload/<id>` resumable state machine end-to-end.

## Required reading (before writing code)

- `backend/reference_server/app.py` — the file under test
- `backend/drive_workspace/tests/test_sqlalchemy_store.py` — the
  existing pattern for backend tests (pytest fixtures, naming, etc.)
- `backend/pyproject.toml` — confirm `flask>=3.0` is a dep (yes via
  `[flask]` extra) and that `pytest-cov` is in `[dev]`
- The Phase 1 outcome's "Verified" section in
  `docs/sessions/2026-04-26-phase1-skeleton.md` — what the curl-level
  contract looks like; reproduce as `test_client` calls

Do not read prior session transcripts.

## In scope

- New file: `backend/reference_server/tests/__init__.py`
- New file: `backend/reference_server/tests/conftest.py` —
  `client` fixture from `app.test_client()`
- New file: `backend/reference_server/tests/test_health.py`:
  - GET /health returns 200 with `{"status":"ok"}`
- New file: `backend/reference_server/tests/test_initiate.py`:
  - POST /api/drive/initiate-upload with valid body returns 200, has
    keys `upload_url`, `drive_file_id`, `expires_at`
  - `drive_file_id` starts with `fake-`
  - `upload_url` resolves to the same host as the request
  - Two consecutive initiates produce different `drive_file_id`s
- New file: `backend/reference_server/tests/test_stub_upload.py`:
  - PUT to unknown upload_id returns 404
  - PUT with full file in one chunk (Content-Range: bytes 0-N/N+1)
    returns 200 with `{"id": "fake-..."}`
  - Two consecutive partial PUTs (Content-Range: bytes 0-99/200, then
    bytes 100-199/200) return 308 then 200; intermediate 308 has
    `Range: bytes=0-99`
  - Out-of-order PUT (skip ahead) — server's behavior: takes max of
    `received` and `end+1`. Test asserts the 308 reports the actual
    high-water mark.
  - PUT after final 200 → 404 (session was popped from `_sessions` map)
  - PUT without Content-Range — server treats as full single-shot;
    test the path
- All tests use `app.test_client()` — no real network, no MockWebServer
  needed (this IS the server).

## Out of scope

- Concurrency tests (threaded PUTs racing). The in-memory `_lock`
  is correct; we'll trust it. If/when Phase 2B replaces the in-memory
  state, those tests would matter; not now.
- Tests against a real server process (subprocess + curl). Out of
  scope for unit tests; integration tests (Phase 3.2) cover that.
- Refactoring the production code. If a test reveals a real bug,
  FIX it in a separate commit and document in this session's Outcome.

## Definition of done

- [ ] `pytest backend/` runs green; new tests counted in the total
- [ ] `pytest --cov=reference_server backend/reference_server/tests/`
      shows ≥90% line coverage on `reference_server/app.py`
- [ ] `mypy --strict drive_workspace/` still green (the reference
      server isn't type-checked under drive_workspace, but verify
      nothing regressed)
- [ ] `ruff check .` from `backend/` is clean
- [ ] One commit. Message references this brief filename.

## Notes / open questions

1. **Should `reference_server` be `mypy --strict`?** Not currently
   in the strict scope (only `drive_workspace/` is). Recommend
   keeping it out for now — the reference server is a demo, not a
   library. If the test files get gnarly enough to want strict
   typing, add `tests/*` to the strict scope and clean up; otherwise
   leave it.
2. **Coverage threshold** — 90% is a reasonable target. The `_lock`
   contention path is hard to cover without threads; document any
   uncovered lines in the Outcome.

## Outcome

> Filled in at end of session.

(blank — to be completed)
