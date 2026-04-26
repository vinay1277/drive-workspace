# Session: 2026-05-05 — Phase 2B prerequisites (make_blueprint + shared_drive_id)

> **Code session, pre-Phase-2B.** Closes the two prerequisite gaps the
> SmartMeter integration sketch (`2026-05-03-smartmeter-integration-sketch`)
> surfaced. Both are pure-code work and have no dependency on Path A
> migration; doing them now means Phase 2B opens with a clean slate
> instead of paying these costs at the worst possible time (when Google
> verification has just cleared and there's pressure to ship).

## Goal

By end of session:

1. `DriveWorkspace.__init__` accepts a `shared_drive_id: str` parameter
   (validated non-empty, fail-fast at construction). ADR-0011 alignment.
2. `drive_workspace.adapters.flask.make_blueprint(dw, auth_decorator)`
   ships, mounting two routes (`POST /api/drive/initiate-upload`,
   `POST /api/drive/submission`) per `docs/BACKEND_CONTRACT.md`.
3. The SmartMeter sketch (`integration-tests/smartmeter/flask_glue_sketch.py`)
   collapses its hand-wired blueprint to a one-line `register_blueprint(...)`,
   proving the gap closed end-to-end.

The two changes are tightly coupled — `make_blueprint` needs to thread
`shared_drive_id` through to the underlying calls — so they ship in one
session.

## Required reading (before writing code)

- `docs/sessions/2026-05-03-smartmeter-integration-sketch.md` Outcome
  (the gaps this session closes; do not re-read the brief, just the
  Outcome section)
- `docs/decisions/0011-sa-storage-quota.md` Implementation notes (Shared
  Drives flag checklist, env var names, role)
- `docs/decisions/0004-modular-package-with-host-plugins.md` (the
  `make_blueprint` signature is mentioned here; this session ships the
  real thing)
- `docs/BACKEND_CONTRACT.md` (URL paths, JSON request/response shapes
  the blueprint must implement)
- `backend/drive_workspace/workspace.py` (the constructor being
  extended)
- `backend/drive_workspace/adapters/flask.py` (one-line stub today;
  this session writes the real impl)
- `backend/reference_server/app.py` (the wire shape `make_blueprint`
  must match — the reference server stays as-is; the package-level
  blueprint mirrors its contract)
- `integration-tests/smartmeter/flask_glue_sketch.py` (the host glue
  that gets simplified at the end of this session)

Do not read prior session transcripts.

## In scope

### `DriveWorkspace.__init__` adds `shared_drive_id`

- New parameter `shared_drive_id: str` after `root_folder_id`.
- Validate non-empty at construction; raise `ValueError` (matching the
  fail-fast posture `FileAuthenticator` uses for missing key files).
- Stored as a public attribute `self.shared_drive_id`.
- No call sites use it yet (Phase 2B implements `FolderManager.provision`
  / `UploadSessionMint.initiate`); the parameter just lands so Phase 2B
  can pick it up without churning the constructor again.
- Update `docs/architecture.md` §8 sketch to include the parameter.
- One unit test in `backend/drive_workspace/tests/test_workspace.py`
  (new file) asserting empty/whitespace `shared_drive_id` raises.

### `drive_workspace.adapters.flask.make_blueprint`

Signature:
```python
def make_blueprint(
    dw: DriveWorkspace,
    auth_decorator: Callable[[F], F] | None = None,
    url_prefix: str = "/api/drive",
) -> Blueprint: ...
```

- Two routes:
  - `POST {url_prefix}/initiate-upload[?count=N]` — calls
    `dw.uploads.initiate(principal_id=..., files=[FileSpec * count])`.
    Response: `{"sessions": [...]}` per `BACKEND_CONTRACT.md`.
  - `POST {url_prefix}/submission` — calls
    `dw.logs.append(principal_id=..., row=payload)`. Response:
    `{"ok": true}`.
- `principal_id` is read from `flask.g.principal_id` (the host's
  decorator is responsible for setting it; the package documents this
  contract).
- `auth_decorator` is optional — wraps both view functions if supplied;
  hosts that don't pass one get raw routes (useful for tests).
- Validation: `count` must be `int` in `[1, MAX_PREFETCH_COUNT]`; 400
  with `{"error": "..."}` on violation. Reuses the cap constant from
  the reference server (move to a shared module if cleaner).
- Type-checked under `mypy --strict`; ruff clean.
- Tests in `backend/drive_workspace/tests/test_flask_adapter.py`
  using `flask.Flask().test_client()` and a fake `DriveWorkspace`
  whose `uploads.initiate` and `logs.append` return canned values
  (no real Drive). Cover: happy paths, count cap, missing
  principal_id, auth decorator wraps both routes.

### `MAX_PREFETCH_COUNT` constant placement

Currently `backend/reference_server/app.py::MAX_PREFETCH_COUNT = 50`.
The package-level blueprint needs the same cap. Move to
`drive_workspace/__init__.py` as the canonical home; reference server
imports from there. Update `BACKEND_CONTRACT.md` to point at the new
location.

### SmartMeter sketch update

- `integration-tests/smartmeter/flask_glue_sketch.py`:
  - Replace the hand-wired `Blueprint(...)` + two `@bp.post` view
    functions with one `app.register_blueprint(make_blueprint(dw,
    auth_decorator=...))` call.
  - Drop the placeholder `_placeholder_require_surveyor_auth` and
    `_placeholder_get_surveyor_context` stubs — `make_blueprint`'s
    contract is that the host's decorator sets `flask.g.principal_id`,
    so the placeholder for that decorator stays (a no-op decorator
    that sets `g.principal_id = "0"` is enough for the sketch to
    type-check).
  - Pass `dw.shared_drive_id` into the constructor via the env var
    captured by `required_env_vars()`.
- Update `integration-tests/smartmeter/README.md`:
  - Move Gaps 1 + 2 from "Surprises / gaps" to a "Closed in
    `2026-05-05-phase2b-prereqs`" subsection.
  - Update the line counts (host glue should drop ~50 lines).
- Update `docs/plan.md` "Open work outside the phase plan" — strike
  the two closed bullets, leave Gaps 3 + 4.

## Out of scope

- Implementing `FolderManager.provision`, `UploadSessionMint.initiate`,
  or `SpreadsheetLogger.append`. They still raise `NotImplementedError`
  per the Phase 2 stub contract; this session lands only the surfaces
  Phase 2B will fill.
- The Shared Drives flag checklist code change in Phase 2B's
  Drive-API call sites. ADR-0011 documents what those need to do; this
  session doesn't run any Drive calls.
- A FastAPI adapter. Phase 2B problem if a host asks.
- The `LogSchema` `TypedDict` (Gap 3) — Phase 3 documentation task.
- The `drive_workspace.migrations` helper (Gap 4) — Phase 4 polish.
- Migrating SmartMeter for real (Phase 4).

## Definition of done

- [ ] `DriveWorkspace.__init__` accepts `shared_drive_id`; empty value
      raises `ValueError`.
- [ ] `backend/drive_workspace/tests/test_workspace.py` exists and
      passes; covers the new validation.
- [ ] `drive_workspace.adapters.flask.make_blueprint(dw,
      auth_decorator)` exists; mounted blueprint serves both routes.
- [ ] `backend/drive_workspace/tests/test_flask_adapter.py` exists and
      passes; covers happy paths, count cap, missing-principal-id, and
      auth decorator application.
- [ ] `MAX_PREFETCH_COUNT` lives in `drive_workspace/__init__.py`;
      reference server imports from there; `BACKEND_CONTRACT.md`
      points at the new location.
- [ ] `integration-tests/smartmeter/flask_glue_sketch.py` uses
      `make_blueprint`; the placeholder auth/context stubs that the
      blueprint replaces are deleted.
- [ ] `integration-tests/smartmeter/README.md` updated to mark Gaps 1
      and 2 closed; line counts re-measured.
- [ ] `docs/plan.md` "Open work outside the phase plan" — Gaps 1 and 2
      bullets struck; Gaps 3 and 4 remain.
- [ ] `docs/architecture.md` §8 sketch shows `shared_drive_id`.
- [ ] `pytest backend/` green (existing 38 + new tests).
- [ ] `mypy --strict drive_workspace/` clean.
- [ ] `mypy --strict integration-tests/smartmeter/` clean.
- [ ] `ruff check .` from `backend/` clean.
- [ ] One commit per logical chunk (likely 3 commits: ctor change +
      adapter impl + sketch update). Final commit references this
      brief filename.

## Notes / open questions

1. **`flask.g.principal_id` as the contract** — the package-level
   blueprint can't know the host's auth shape. Recommend pinning
   that the host's decorator is responsible for setting
   `g.principal_id: str` before the view runs; document in the
   adapter module's docstring. The `auth_decorator=` parameter is
   optional precisely so tests can run without an auth layer (and
   set `g.principal_id` directly via `before_request` in the test
   harness).
2. **`url_prefix`** — defaults to `/api/drive`. Hosts that mount
   under a different prefix override; `BACKEND_CONTRACT.md` documents
   the canonical default.
3. **Shared `MAX_PREFETCH_COUNT`** — moving from the reference server
   is the cleaner long-term home. Reference server tests need to
   update their import path; small mechanical change.
4. **404 vs 401 vs 400** — the brief assumes the host's
   `auth_decorator` raises whatever the host's policy says (401 in
   most cases). The blueprint itself never returns 401 — it
   returns 400 only for malformed `count` and 200 otherwise. Document
   this asymmetry in the adapter module's docstring.

## Outcome

Both Phase 2B prerequisites landed. The SmartMeter sketch was
updated end-to-end and now uses the real `make_blueprint`, proving
the gaps closed.

**Shipped (3 commits)**

1. `feat(workspace): add shared_drive_id to DriveWorkspace constructor`
   — new parameter after `root_folder_id`, validated non-empty
   (rejects `""` and whitespace) → `ValueError`. Stored as public
   `self.shared_drive_id`. New `backend/drive_workspace/tests/test_workspace.py`
   covers the validation. `docs/architecture.md` §8 sketch updated.
2. `feat(adapters): ship drive_workspace.adapters.flask.make_blueprint`
   — full impl mounting `POST {url_prefix}/initiate-upload[?count=N]`
   and `POST {url_prefix}/submission` per `BACKEND_CONTRACT.md`.
   Default `url_prefix=/api/drive`. Reads `principal_id` from
   `flask.g.principal_id` (host contract). Optional `auth_decorator`
   wraps both views. `MAX_PREFETCH_COUNT` moved to
   `drive_workspace/__init__.py`; reference server re-exports for
   import-path stability. `BACKEND_CONTRACT.md` updated. New
   `test_flask_adapter.py` with 12 cases.
3. `chore(integration-tests): swap SmartMeter sketch to make_blueprint`
   — collapsed hand-wired blueprint to one
   `register_blueprint(make_blueprint(dw, auth_decorator=...))` call;
   threaded `shared_drive_id` from `required_env_vars()`. Sketch's
   `flask_glue_sketch.py` dropped from 148 → 91 lines. README and
   plan.md mark Gaps 1 and 2 closed.

**Open questions resolved (per maintainer instruction "you take call")**

1. `flask.g.principal_id` is the contract; documented in adapter
   module docstring.
2. `url_prefix` default is `/api/drive`.
3. `MAX_PREFETCH_COUNT` lives in `drive_workspace/__init__.py`;
   reference server imports + re-exports it.
4. Blueprint never returns 401. 400 only for malformed `count`.
   Missing `g.principal_id` is a host contract violation; surfaces
   as Flask's default 500. A test (`test_missing_principal_id_surfaces_as_500`)
   locks in that behaviour.

**Verification**

- `pytest backend/`: 56 passed, 1 skipped (38 prior + 6 new
  `test_workspace.py` cases + 12 new `test_flask_adapter.py` cases).
- `mypy --strict drive_workspace/`: clean (20 source files).
- `mypy --strict integration-tests/smartmeter/` (run from
  `backend/`): clean (5 source files).
- `ruff check .`: clean.

**Out of scope (per brief, unchanged)**

- `FolderManager.provision`, `UploadSessionMint.initiate`,
  `SpreadsheetLogger.append` still raise `NotImplementedError` — Phase 2B.
- Shared-Drive flag plumbing at Drive API call sites — Phase 2B.
- FastAPI adapter — deferred until a host asks.
- Gaps 3 (`LogSchema` payload `TypedDict`) and 4
  (`drive_workspace.migrations`) remain open in `plan.md`.
