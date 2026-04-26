# Session: 2026-05-03 — SmartMeter integration sketch (Phase 4 dry run)

> **Design-shaped session.** Phase 4 (real SmartMeter integration) is
> gated on `v0.1.0`, which won't ship until Phase 3 closes. But the
> SmartMeter glue (~80 lines) can be sketched now to confirm the
> drive_workspace plug points actually fit SmartMeter's existing tables
> and JWT shape. If they don't, we find out *while the package can
> still flex*, not after a v0.1.0 freeze.

## Goal

By end of session: a sketch directory `integration-tests/smartmeter/`
contains:

1. `smartmeter_principal_store.py` — a `PrincipalStore` impl wrapping
   SmartMeter's existing `mobile_surveyor_logins` table (or whichever
   surveyor table is canonical — confirm by reading SmartMeter's code).
2. `smartmeter_log_schema.py` — a `LogSchema` impl with columns:
   timestamp, ivrs_no, consumer_name, photo_link, audio_link,
   video_link, gps_lat, gps_lng, status.
3. `smartmeter_authenticator.py` — confirms the SA loading pattern
   that ADR-0011 settles on works against SmartMeter's secret-storage
   convention (env var? mounted file? per ADR-0011's choice).
4. `flask_glue_sketch.py` — the ~20-line route file that wraps
   `make_blueprint(...)` (or hand-wires the routes) around the host's
   auth middleware.
5. `integration-tests/smartmeter/README.md` — what was confirmed,
   what was surprising, what `drive_workspace` package surface gaps
   were found (add as plan.md tasks if any).

The deliverable is *the sketch and the findings*, not a working
integration. Nothing imports SmartMeter for real; the glue files type-
and lint-check against `drive_workspace` only, with SmartMeter's
schemas/JWT shapes hand-translated as comments.

## Required reading (before writing code)

- `docs/architecture.md` §7 (component view) and §8 (public API sketch)
- `docs/decisions/0004-modular-package-with-host-plugins.md` (the
  contract host writes against)
- `backend/drive_workspace/stores/protocol.py` (`PrincipalStore`)
- `backend/drive_workspace/logs.py` (`LogSchema`, `ColumnSpec`)
- `backend/drive_workspace/auth.py` (`FileAuthenticator`)
- Whatever ADR-0011 decided (likely
  `docs/decisions/0011-sa-storage-quota.md`)
- SmartMeter codebase at `D:/Python/Meter/SmartMeter_2/`:
  - `verticals/google_drive/google_auth.py` — current Drive auth
    (OAuth flow, will be replaced by drive_workspace)
  - `verticals/google_drive/config.py` — current config
  - The surveyor table — find it via `grep -r "mobile_surveyor" .` or
    similar
  - The JWT + auth middleware — find via
    `grep -r "X-Device-Token" verticals/`

Do not read prior session transcripts.

## In scope

### `integration-tests/smartmeter/smartmeter_principal_store.py`

- ~30 lines.
- Class `SmartMeterPrincipalStore` implementing `PrincipalStore` Protocol.
- Wraps SmartMeter's existing surveyor table — use surveyor_id (the
  primary key) as `principal_id`.
- The `folder_id` and `spreadsheet_id` get added as new columns; the
  sketch documents the migration in the file's docstring.
- No SQLAlchemy ORM mapping (SmartMeter uses raw connectors); use
  direct SQL via `DatabaseManager` (mimic SmartMeter's pattern).

### `integration-tests/smartmeter/smartmeter_log_schema.py`

- ~20 lines.
- Class `SmartMeterLogSchema` with the columns listed in Goal.
- `render_row` maps a survey-submission dict (keys: timestamp,
  ivrs_no, consumer_name, photo_id, audio_id, video_id, gps, status)
  to the column list with `=HYPERLINK(...)` formula cells for the
  `_id` fields.

### `integration-tests/smartmeter/smartmeter_authenticator.py`

- ~10-15 lines depending on ADR-0011's choice.
- If file-based: just instantiate `FileAuthenticator(env_var_path)`.
- If DWD: same plus `subject=os.environ["DRIVE_WORKSPACE_DWD_SUBJECT"]`.
- Document SmartMeter's expected env-var names (likely matches
  existing Gmail vertical conventions for symmetry).

### `integration-tests/smartmeter/flask_glue_sketch.py`

- ~20-25 lines.
- Shows the full integration: a Flask app instance with auth
  middleware, the drive_workspace blueprint (or hand-wired routes)
  mounted, and the survey-submission hook calling `dw.logs.append(...)`.
- Doesn't actually run; it's a code sketch that imports, type-checks,
  and lint-checks. Mark as `# type: ignore[import]` where SmartMeter
  imports would be (since drive_workspace doesn't depend on
  SmartMeter).

### `integration-tests/smartmeter/README.md`

- What this sketch proves.
- The exact line-count of each file (lines of host glue that v0.1.0
  promises stays under 100).
- Surprises found (gaps in `drive_workspace` plug points; mismatches
  with SmartMeter's actual conventions).
- Migration notes: what columns SmartMeter's surveyor table needs
  added, what env vars need set, what DB migrations are needed.

## Out of scope

- Anything that imports or runs against the actual SmartMeter codebase
  (we're sketching, not integrating).
- Migrating SmartMeter's existing data. Phase 4 problem.
- The Android side of SmartMeter (the existing app continues using its
  current Drive code until v0.1.0 ships and Phase 4 happens).
- Implementing `make_blueprint` if it doesn't exist yet — sketch
  hand-wired routes if so, and add a plan.md task for the
  blueprint.

## Definition of done

- [ ] All five files above exist under `integration-tests/smartmeter/`
- [ ] Each Python file imports cleanly under
      `python -c "import integration_tests.smartmeter.<name>"` from a
      venv with `drive_workspace` installed (NOT SmartMeter installed)
- [ ] `mypy --strict integration-tests/smartmeter/` clean (with
      `# type: ignore[import]` on SmartMeter symbols only)
- [ ] `ruff check integration-tests/smartmeter/` clean
- [ ] README documents findings; if package gaps found, plan.md gets
      new tasks under "Open work outside the phase plan"
- [ ] One commit. Message references this brief filename.

## Notes / open questions

1. **SmartMeter table for surveyors** — the path is
   `D:/Python/Meter/SmartMeter_2/`. Find the canonical surveyor
   table name first; the sketch uses what's actually there.
2. **JWT shape** — drive_workspace doesn't authenticate; it trusts
   the host. The sketch just shows the host's auth decorator
   wrapping the routes. Don't over-design.
3. **`make_blueprint`** — does
   `drive_workspace.adapters.flask.make_blueprint` exist yet?
   Probably not (Phase 2A left adapters/flask.py empty). If absent,
   sketch hand-wired routes; add a plan.md task to ship
   `make_blueprint` as part of Phase 2B.
4. **Per-principal folder lifecycle** — onboarding a new surveyor:
   when does `dw.principals.provision(...)` run? Recommend: in
   SmartMeter's existing surveyor-creation flow, as a hook. Sketch
   this in the README.

## Outcome

> Filled in at end of session.

(blank — to be completed)
