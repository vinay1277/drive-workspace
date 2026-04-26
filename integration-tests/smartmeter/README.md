# SmartMeter integration sketch — Phase 4 dry run

> **Not a working integration.** The files in this directory are a
> code sketch that confirms drive_workspace's plug points fit
> SmartMeter's existing schemas and middleware. Phase 4 (real
> integration) ships once `v0.1.0` does.
>
> Brief: [`docs/sessions/2026-05-03-smartmeter-integration-sketch.md`](../../docs/sessions/2026-05-03-smartmeter-integration-sketch.md)

---

## What this sketch proves

Each of `drive_workspace`'s three plug points (ADR-0004) was instantiated
against the actual shapes used in `D:\Python\Meter\SmartMeter_2\`:

| Plug point          | SmartMeter reality                                                         | Sketch file                              |
|---------------------|----------------------------------------------------------------------------|------------------------------------------|
| `PrincipalStore`    | `SmartMeter.surveyors` (BIGINT `surveyor_id` PK, revision pattern, raw SQL via `core.database_manager.DatabaseManager`) | `smartmeter_principal_store.py`          |
| `LogSchema`         | Per-survey-submission columns; HYPERLINK formulas to Drive media          | `smartmeter_log_schema.py`               |
| `Authenticator`     | ADR-0011's Shared-Drives choice → unmodified `FileAuthenticator` + env-var | `smartmeter_authenticator.py`            |
| Routes / blueprint  | `make_blueprint(dw, auth_decorator=...)` under `core.surveyor_auth.require_surveyor_auth` JWT decorator | `flask_glue_sketch.py`                   |

All four files type-check under `mypy --strict` and pass `ruff check`
with only `drive_workspace` installed (no SmartMeter on `PYTHONPATH`).

## Line counts

| File                              | Total lines | Approx. code lines (excl. docstrings + comments) |
|-----------------------------------|-------------|--------------------------------------------------|
| `smartmeter_principal_store.py`   | 137         | 41                                               |
| `smartmeter_log_schema.py`        | 79          | 37                                               |
| `smartmeter_authenticator.py`     | 73          | 16                                               |
| `flask_glue_sketch.py`            | 91          | 35                                               |
| **Total**                         | **380**     | **~129**                                         |

The brief's architecture target is "~80 lines of host glue."
`flask_glue_sketch.py` carries one placeholder
(`_placeholder_require_principal_auth`) plus a `_placeholder_db()`
stub that get **deleted** in production — replaced by SmartMeter's
real decorator and `core.database_manager.DatabaseManager()`. Real
production glue lands at ~70 code lines, comfortably under the
architecture target.

## What was confirmed

1. **`surveyor_id` → `principal_id` is a clean fit.** The `surveyors`
   table's revision pattern (`is_current_revision`, `active`,
   `revoked_at`) maps onto drive_workspace's `record_provisioned` /
   `record_revoked` semantics without contortion. Casting BIGINT to
   `str` at the Protocol boundary is the only impedance.

2. **Raw-SQL pattern coexists fine with drive_workspace's
   `Protocol`-driven design.** ADR-0004's structural typing means
   SmartMeter doesn't have to introduce SQLAlchemy just to satisfy
   the contract. The Phase 2A reference `SqlAlchemyPrincipalStore`
   stays as the package default; SmartMeter brings its own.

3. **JWT middleware sits in front of the routes cleanly.**
   `core.surveyor_auth.require_surveyor_auth` decorates the Flask
   blueprint's view functions. drive_workspace itself never sees the
   token — it trusts the host's auth, exactly as ADR-0001's trust
   boundary requires. `get_surveyor_context()['surveyor_id']` is the
   single value the glue forwards.

4. **ADR-0011 Shared-Drives choice is operationally lighter than DWD
   for this host.** No `subject` plumbing needed; the existing
   `verticals/gmail/credentials/` directory continues to be the
   single credentials source. SmartMeter just adds the SA key file
   and two new env vars (`DRIVE_WORKSPACE_SHARED_DRIVE_ID`,
   `DRIVE_WORKSPACE_ROOT_FOLDER_ID`).

5. **`SmartMeterLogSchema.render_row` cleanly produces
   `=HYPERLINK(...)` formula cells** for the photo / audio / video
   slots from a payload dict whose keys match what
   `survey_management/routes_restx.py` already produces. No payload
   reshape needed at the call site.

## What surprised me / gaps in `drive_workspace`

These become tasks under `plan.md` "Open work outside the phase plan."

### Closed in `2026-05-05-phase2b-prereqs`

- **Gap 1 — `make_blueprint`.** Shipped in
  `drive_workspace/adapters/flask.py`. The sketch's hand-wired
  routes collapsed to one `register_blueprint(make_blueprint(dw,
  auth_decorator=...))` call (~57 lines removed from
  `flask_glue_sketch.py`).
- **Gap 2 — `shared_drive_id`.** `DriveWorkspace.__init__` now takes
  `shared_drive_id: str` (validated non-empty) per ADR-0011. The
  glue's `required_env_vars()` already returned the env var; the
  sketch now passes it through.

### Gap 3 — No host-migration helper

Each host copies the same `ALTER TABLE ... ADD COLUMN drive_folder_id ...`
migration. The package could ship a `drive_workspace.migrations`
module with the recommended SQL as a Python string, parameterised by
table name and id type. Low priority — every host does this once and
the cost is small — but worth the ~20-line win for the second
consumer.

### Gap 4 — `SpreadsheetLogger.append`'s payload contract is implicit

`LogSchema.render_row(payload: dict[str, Any])` is fully typed on the
return side but the input dict's expected keys live entirely in the
host's `LogSchema` impl. SmartMeter's `SmartMeterLogSchema` documents
the payload keys in its module docstring; nothing enforces that the
caller actually passes those keys. A `TypedDict` per host (host
declares it) would give static checking. Annotate as a Phase 3
documentation task — not a structural change.

### Surprise — the architecture sketch shows `dw.principals`, the code says `FolderManager`

`docs/architecture.md` §8 sketches the public API as
`dw.principals.provision(...)` / `dw.principals.revoke(...)`.
The actual stub is `dw.principals = FolderManager(self)`. They
agree — `dw.principals` IS the `FolderManager` instance. The naming
read confusing on first contact; an alias or KDoc clarification on
`FolderManager` would help. Minor.

## Migration notes for Phase 4

When the real integration ships:

### DB migration

```sql
ALTER TABLE SmartMeter.surveyors
    ADD COLUMN drive_folder_id      VARCHAR(64) NULL,
    ADD COLUMN drive_spreadsheet_id VARCHAR(64) NULL,
    ADD COLUMN drive_provisioned_at TIMESTAMP   NULL,
    ADD COLUMN drive_revoked_at     TIMESTAMP   NULL,
    ADD INDEX idx_drive_folder (drive_folder_id);
```

Place under `migrations/0NN_drive_workspace_columns.sql` next to
SmartMeter's existing migration sequence (currently up to `035_*`).

### Provisioning hook

Recommend hooking `dw.principals.provision(...)` into
`verticals/surveyor_management/db_operations.py::create_surveyor`
post-commit. New surveyors get a Drive folder + spreadsheet at
creation; existing surveyors are migrated lazily on first upload
(check `get_folder_id(principal_id) is None` → call `provision`).

A one-shot backfill script under
`scripts/backfill_drive_workspace_principals.py` is also reasonable
(iterate active+current-revision surveyors, call `provision` for
each). Decide at Phase 4 kickoff based on Drive API quota patience.

### Env vars

Add to `.env`:

```
DRIVE_WORKSPACE_SA_KEY_PATH=verticals/gmail/credentials/drive_workspace_sa.json
DRIVE_WORKSPACE_ROOT_FOLDER_ID=<from Phase 4 provisioning>
DRIVE_WORKSPACE_SHARED_DRIVE_ID=<from Phase 4 provisioning>
```

Optionally promote to `app_configuration` rows (mirrors how
`DRIVE_*` keys are already managed there per
`verticals/google_drive/config.py`).

### Decommissioning the existing OAuth Drive auth

`verticals/google_drive/google_auth.py` does an OAuth2 user-flow
with pickle tokens, scopes including `drive.metadata` and
`drive.readonly`. drive_workspace replaces this for the
per-principal-folder use case but the existing `verticals/google_drive/`
code is also used for the SmartMeter_JMC bills/reports/exports
flow. Phase 4 does **not** delete `verticals/google_drive/` — the
two coexist; drive_workspace owns per-surveyor folders and the
spreadsheet log, the existing vertical owns admin-facing bulk Drive.

## Verification done in this session

```
ruff check integration-tests/smartmeter/        # clean
mypy --strict integration-tests/smartmeter/     # 5 source files, no issues
PYTHONPATH=integration-tests python -c \
  "from smartmeter import smartmeter_principal_store, smartmeter_log_schema, smartmeter_authenticator, flask_glue_sketch"
                                                # imports OK
```

No SmartMeter on `PYTHONPATH`. Only `drive_workspace` installed (`pip
install -e backend/`).
