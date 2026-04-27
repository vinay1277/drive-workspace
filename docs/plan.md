# Plan

> **Status**: living document. Updated every session that completes or adds tasks.
> **Source of truth for**: what we're doing next, what's blocked, what's done.
> **Not source of truth for**: architecture (see [`architecture.md`](architecture.md)) or rationale (see [`decisions/`](decisions/)).

---

## Phasing overview

| Phase | Goal | Done when |
|-------|------|-----------|
| **1. Skeleton** | Repo structure stood up; package + reference server boot; tester app ported; everything mocked, nothing real. | `docker compose up && ./gradlew :tester:installDebug && tap upload` returns a fake-success end-to-end. |
| **2. Real Drive** | SA wiring, folder lifecycle, resumable session minting, spreadsheet logger, reconciliation. | Tester uploads a real file; appears in real Drive in the right per-principal folder; spreadsheet row appears with clickable hyperlink. |
| **3. Hardening** | Tests filled in; mypy strict green; docs complete; ADRs reviewed; v0.1.0 tagged. | Maturity checklist (below) passes. |
| **(later) 4. Integration** | SmartMeter pins v0.1.x and writes its glue. | SmartMeter beta upload through this stack. |

## Phase 1 — Skeleton

**Goal**: prove the structure holds before any Drive logic is written.

| # | Task | Owner | Depends on | Status |
|---|------|-------|------------|--------|
| 1.1 | Create `backend/drive_workspace/` package skeleton: empty modules (`workspace.py`, `folders.py`, `uploads.py`, `logs.py`, `reconcile.py`), `stores/`, `adapters/`, `__init__.py` re-exports. | 2026-04-26 | — | done |
| 1.2 | Create `backend/reference_server/`: minimal Flask app with `GET /health` and stub `POST /api/drive/initiate-upload` that returns a hard-coded fake session. | 2026-04-26 | 1.1 | done |
| 1.3 | `docker-compose.yml`: postgres 16 + reference_server. `docker compose up` works. | 2026-04-26 | 1.2 | done |
| 1.4 | Move `:core:drive` from SmartMeter V2 worktree → `android/library/`. Move `:sample:drive-tester` → `android/tester/`. Update package paths + Gradle settings. | 2026-04-26 | — | done |
| 1.5 | `android/gradle/libs.versions.toml` — copy / adapt from V2 worktree. | 2026-04-26 | 1.4 | done |
| 1.6 | Tester app: point default backend URL at the reference server (`10.0.2.2:8080` for emulator). Upload one file end-to-end against the stub server. | 2026-04-26 | 1.2, 1.4 | done |
| 1.7 | `.github/workflows/backend-ci.yml`: lint + test on push. (Android CI deferred to Phase 3.) | 2026-04-26 | 1.1 | done |
| 1.8 | `backend/README.md`: how to run locally, how to run tests. | 2026-04-26 | 1.1, 1.2, 1.3 | done |

**Phase 1 exit criterion**: a fresh clone, `docker compose up`, `./gradlew :tester:installDebug`, tester taps Upload — fake session is minted by reference server, Android library "uploads" to a stub URL the reference server also serves, gets a fake 200 back, displays Succeeded. Zero Drive involvement.

**Phase 1 status: closed end-to-end on 2026-04-26.** Tester app on a Samsung
SM-M526B uploaded a 279 KB image through the Flask reference server (run
directly via `flask run`, not via docker — Docker Desktop install on the
dev box is deferred). Two main-thread-network bugs fixed during
verification (commits `35202e7`, `c03a4b1`). Full details in
[`sessions/2026-04-26-phase1-skeleton.md`](sessions/2026-04-26-phase1-skeleton.md)
"Follow-up verification" section.

## Phase 2 — Real Drive

**Goal**: wire up real Drive credentials and prove the full upload path.

| # | Task | Status |
|---|------|--------|
| 2.1 | Provision the test Workspace + service account + test root folder. Document in `docs/deployment.md`. | not started |
| 2.2 | `Authenticator` impl: load SA credential from file path, env, or callable. | done (file path; env/callable deferred until a host needs them) |
| 2.3 | `FolderManager.provision()`: create folder from template, share view-only, persist mapping via `PrincipalStore`. | not started |
| 2.4 | `FolderManager.revoke()`: drop share; folder remains. | not started |
| 2.5 | `UploadSessionMint.initiate()`: real `POST /upload/drive/v3/files?uploadType=resumable` to Drive; persist audit row. | not started |
| 2.6 | Default `SqlAlchemyPrincipalStore`: schema migrations, basic CRUD. | done (CRUD; Alembic migrations deferred to Phase 3) |
| 2.7 | `LogSchema` protocol + reference impl. `SpreadsheetLogger.append()` via Sheets API. | partial (Protocol + ColumnSpec + reference impl done; Sheets `append` is Phase 2B) |
| 2.8 | `ReconciliationRunner` + `python -m drive_workspace.reconcile` CLI. Orphan detection + cleanup. | not started |
| 2.9 | Reference server wires real `DriveWorkspace`. Tester app uploads real file into real Drive, observed by browsing drive.google.com. | not started |
| 2.10 | Session prefetch bank: extend backend endpoint with `count` param; library stores + draws from local bank. | not started |

**Phase 2 exit criterion**: tester app uploads a 10 MB photo, the file appears in `/Principals/<test-user>/photos/` in the test Drive, a row appears in the test spreadsheet with a clickable hyperlink, reconciliation CLI run against an orphaned session correctly identifies it.

## Phase 3 — Hardening

| # | Task | Status |
|---|------|--------|
| 3.1 | `drive_workspace/tests/` — unit tests with `responses` mocking Drive/Sheets APIs. ≥85% line coverage on package code. | not started |
| 3.2 | `integration-tests/` — at least three end-to-end tests: happy path, mid-stream disconnect, session expiry + re-init. Run against real test Drive in CI. | not started |
| 3.3 | `mypy --strict` clean across `drive_workspace/`. | done (verified clean across 23 source files; CI enforces) |
| 3.4 | API documentation: every public symbol has a docstring; `sphinx` build succeeds. | done (sphinx-build clean under `-W` already; see `2026-05-04-sphinx-docs`) |
| 3.4a | Add `sphinx-build -b html -W` to `.github/workflows/backend-ci.yml` so docstring drift fails CI. | done (added in the post-queue cleanup; CI now installs the `docs` extra and runs `sphinx-build -W`) |
| 3.5 | A second `LogSchema` impl (intentionally different shape) to validate the abstraction. | done (`InspectionLogSchema` fixture + 5 tests; intentionally asymmetric — composed/derived/formula cells, server-rendered `=NOW()`, hyperlink quote-escaping) |
| 3.6 | One contract change exercised end-to-end (e.g. add a metadata field; touch backend, library, integration tests in one PR). | not started |
| 3.7 | `docs/deployment.md` + `docs/integration-guide.md` complete. | not started |
| 3.8 | Tag `v0.1.0`. | not started |

**Phase 3 exit criterion**: maturity checklist below passes.

### Maturity checklist (gate to integration)

- [ ] End-to-end test: tester uploads 30 MB file 10× consecutively, with one forced disconnect and one forced 5xx in the run. All complete successfully. *(blocked on Phase 2B → real Drive)*
- [ ] Reconciliation CLI demonstrably cleans up an orphaned session. *(blocked on Phase 2B)*
- [x] Every public package symbol has a docstring; sphinx build succeeds. *(`-W` clean; CI enforces)*
- [x] Two distinct `LogSchema` implementations exist. *(`ExampleLogSchema`, `InspectionLogSchema`)*
- [ ] One contract change has shipped cleanly across both sides. *(prefetch-bank already covers library + reference server; Drive side touched after Phase 2B)*
- [x] `mypy --strict` and `ruff` green in CI.
- [ ] `v0.1.0` tagged.

## Phase 4 — SmartMeter integration (later, separate work)

Not started. Depends on v0.1.0. Out of scope until the maturity checklist is met. Sketch only:

- Pin `drive_workspace @ git+ssh://...@v0.1.0` in SmartMeter `requirements.txt`.
- Write `SmartMeterPrincipalStore` (~30 lines wrapping existing surveyor table).
- Write `SmartMeterLogSchema` (~15 lines: timestamp, ivrs_no, consumer_name, photo/audio/video links, status).
- Wire `make_blueprint(...)` into SmartMeter's existing Flask routes.
- Add Android library to SmartMeter app's Gradle deps; wire `UploadInitiator`.
- Beta with one division. Production after a week.

## Open work outside the phase plan

- ~~ADR review pass: read all ADRs after Phase 2; supersede any that didn't survive contact with reality.~~ **(Closed in post-queue cleanup; ADRs 0001-0011 reviewed: 0003 had its open question closed and an Implementation-status section added; 0008 got a Status note for Path B reality; 0010 got the chunk-PUT sibling-fix note. None superseded.)**
- ~~Phase 3 task seeded by ADR-0010: add an Android instrumentation test that exercises the full upload path with the flow collected on `Dispatchers.Main`.~~ **(Closed in `2026-05-01-instrumentation-test`; commit `f4ec286` ships the test, `43f3611` fixes the chunk-PUT response-handling bug it surfaced — captured as ADR-0010's sibling-fix note.)**
- ~~**Phase 2B prerequisite**: ship `drive_workspace.adapters.flask.make_blueprint(dw, auth_decorator)`.~~ **(Closed in `2026-05-05-phase2b-prereqs`.)**
- ~~**Phase 2B prerequisite**: thread `shared_drive_id` through `DriveWorkspace.__init__`.~~ **(Closed in `2026-05-05-phase2b-prereqs`.)**
- ~~**Phase 3 documentation task**: per-host `TypedDict` for `LogSchema.render_row` payload.~~ **(Closed in post-queue cleanup; pattern documented in `logs.py` Note section + `ExampleLogPayload` TypedDict shipped in `tests/_fixtures/example_log_schema.py`.)**
- ~~**Phase 4 nice-to-have**: ship `drive_workspace.migrations` helper module.~~ **(Closed in post-queue cleanup; module shipped with 8 tests + sphinx coverage; `principal_columns_alter_sql(table, dialect, ...)` returns dialect-specific ALTER TABLE SQL for postgresql, mysql, sqlite. Now part of `__all__`.)**

## Notes for whoever picks up the next session

- Read [`architecture.md`](architecture.md) and the relevant ADR(s) **before** writing code.
- Read the session brief in [`sessions/`](sessions/) named for the date you're working.
- If a brief doesn't exist for the task you're picking up, **write the brief first**, then start work. The brief is a forcing function for clarity.
- If you discover a decision that should have been an ADR but isn't, write the ADR before continuing.
