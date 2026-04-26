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
| Routes / blueprint  | Hand-wired (Phase 2A `make_blueprint` is a stub) under `core.surveyor_auth.require_surveyor_auth` JWT decorator | `flask_glue_sketch.py`                   |

All four files type-check under `mypy --strict` and pass `ruff check`
with only `drive_workspace` installed (no SmartMeter on `PYTHONPATH`).

## Line counts

| File                              | Total lines | Approx. code lines (excl. docstrings + comments) |
|-----------------------------------|-------------|--------------------------------------------------|
| `smartmeter_principal_store.py`   | 137         | 41                                               |
| `smartmeter_log_schema.py`        | 79          | 37                                               |
| `smartmeter_authenticator.py`     | 73          | 16                                               |
| `flask_glue_sketch.py`            | 148         | 69                                               |
| **Total**                         | **437**     | **~163**                                         |

The brief's architecture target is "~80 lines of host glue."
`flask_glue_sketch.py` is heavier than that because it carries
placeholder stubs for the four SmartMeter symbols
(`DatabaseManager`, `require_surveyor_auth`, `get_surveyor_context`,
plus the boot-wiring helper) that get **deleted** in production —
replaced by direct imports from SmartMeter and one
`make_blueprint(...)` line once Phase 2B ships that helper. Real
production glue is ~120 lines. Within tolerance of the architecture
target; not under it.

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

### Gap 1 — `make_blueprint` doesn't exist yet

`drive_workspace/adapters/flask.py` is a one-line Phase 2 stub. The
sketch hand-wires `Blueprint("drive_workspace", url_prefix="/api/drive")`
with two routes; once `make_blueprint(dw, auth_decorator)` ships, the
glue collapses to:

```python
from drive_workspace.adapters.flask import make_blueprint
app.register_blueprint(make_blueprint(dw, auth_decorator=require_surveyor_auth))
```

That removes ~50 lines from the host and makes the wire contract
(URL paths, JSON shapes) live in one place.

### Gap 2 — `DriveWorkspace.__init__` lacks `shared_drive_id`

ADR-0011 settled on Shared Drives. The Phase 2 stub
`DriveWorkspace.__init__` was written before that ADR and takes
`root_folder_id`, `template_folder_id`, `template_spreadsheet_id` —
no `shared_drive_id`. Phase 2B will need to thread it through; the
glue captures the env var via `required_env_vars()` and passes it
along when the constructor grows the parameter.

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
