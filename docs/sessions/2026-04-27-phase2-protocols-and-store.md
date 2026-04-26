# Session: 2026-04-27 — Phase 2A: Authenticator + default PrincipalStore + LogSchema

> **First Phase 2 session.** Land the host-pluggable scaffolding that does
> *not* require a real Drive Workspace yet: file-backed `Authenticator`,
> default `SqlAlchemyPrincipalStore` with schema + CRUD + tests, and the
> formalized `LogSchema` Protocol with one reference impl. Real Drive REST
> calls (`FolderManager.provision`, `UploadSessionMint.initiate`,
> `SpreadsheetLogger.append`) are deferred to Phase 2B once
> [ADR-0008](../decisions/0008-test-workspace-ownership.md) is accepted.

## Goal

By end of session: `pip install -e backend[dev,flask,postgres]` is enough
to run a backend `pytest` suite that covers `Authenticator`,
`SqlAlchemyPrincipalStore` (against SQLite + against postgres via
docker-compose), and `LogSchema`. `mypy --strict drive_workspace/` stays
clean. The reference server still serves the Phase 1 stubs unchanged —
Phase 2A doesn't switch them over yet.

## Required reading (before writing code)

- `docs/architecture.md` §7 (component view), §8 (public API sketch),
  §11 (stack table)
- `docs/decisions/0004-modular-package-with-host-plugins.md`
- `docs/decisions/0006-stack-choices.md`
- `docs/plan.md` § "Phase 2 — Real Drive" tasks 2.2, 2.6, 2.7
- The Phase 1 outcome at the bottom of
  `docs/sessions/2026-04-26-phase1-skeleton.md`

Do not read prior session transcripts.

## In scope

### `Authenticator`

- `backend/drive_workspace/auth.py` (new module): a concrete
  `FileAuthenticator` class that loads a service-account JSON key from a
  filesystem path and returns a
  `google.oauth2.service_account.Credentials` from `credential()`.
- `Authenticator` Protocol stays in `workspace.py` for now; if it grows
  more impls (env-var, callable), promote to its own module in a later
  session.
- Scope-list constant declared up top
  (`https://www.googleapis.com/auth/drive`,
  `https://www.googleapis.com/auth/spreadsheets`); document why each is
  needed.

### Default `PrincipalStore`

- `backend/drive_workspace/stores/sqlalchemy.py`: replace the empty
  placeholder with `SqlAlchemyPrincipalStore` plus a SQLAlchemy 2.x
  declarative model `Principal(principal_id PK, folder_id, spreadsheet_id,
  display_name, granted_email, provisioned_at, revoked_at)`. CRUD methods
  match the `PrincipalStore` Protocol surface from
  `stores/protocol.py`.
- Use `sqlalchemy.orm.DeclarativeBase`. No Alembic yet — ship a
  `create_all`-style helper for tests; Alembic comes in Phase 3 once the
  schema is stable.
- Constructor takes a `sessionmaker[Session]` so the host owns the
  engine.

### `LogSchema`

- Promote `LogSchema` to a top-level concept: the Protocol stays in
  `logs.py`; add a small `ColumnSpec` value object so `columns()` returns
  enough info to render a header row, and a `render_row` that takes a
  host-supplied dict and returns a `list[Any]` whose length matches
  `columns()`.
- Reference impl `ExampleLogSchema` (timestamp + principal_id + free-text
  note + photo link) lives under
  `backend/drive_workspace/tests/_fixtures/example_log_schema.py` so it's
  available to tests without polluting the package's importable surface.

### Tests

- `backend/drive_workspace/tests/test_auth.py`: unit-tests
  `FileAuthenticator` against a fixture JSON (faked SA key — does not
  contact Google). Verifies path resolution, scope list, and that
  `credential()` returns a `Credentials` instance.
- `backend/drive_workspace/tests/test_sqlalchemy_store.py`:
  - against `sqlite:///:memory:` for fast unit coverage
  - against a real postgres via `docker-compose` (gated behind a
    `DRIVE_WS_POSTGRES_URL` env var so the suite doesn't require Docker
    by default)
  - covers: provision flow (`record_provisioned`), revoke flow
    (`record_revoked`), idempotent re-provision, queries
    (`get_folder_id`, `get_spreadsheet_id`).
- `backend/drive_workspace/tests/test_log_schema.py`: verifies
  `ExampleLogSchema.render_row` matches `columns()` length and produces a
  predictable shape.

### CI

- Update `.github/workflows/backend-ci.yml` to remove the "exit 5 = OK"
  pytest workaround now that the suite has real tests.

## Out of scope

- **Anything that calls Drive or Sheets APIs.** That waits for ADR-0008.
  Specifically: `FolderManager.provision`, `FolderManager.revoke`,
  `UploadSessionMint.initiate`, `SpreadsheetLogger.append`,
  `ReconciliationRunner.run` all still raise `NotImplementedError`.
- **Alembic migrations.** Phase 3.
- **Reference server endpoints upgraded to use real `DriveWorkspace`.**
  The Phase 1 stub endpoints stay; flipping them to real is Phase 2B.
- **Session prefetch bank** (Phase 2.10).
- **Android changes.** Zero touch on `android/` this session.

## Definition of done

- [ ] `backend/drive_workspace/auth.py` exists with `FileAuthenticator`.
- [ ] `backend/drive_workspace/stores/sqlalchemy.py` implements
      `SqlAlchemyPrincipalStore` matching the
      `stores/protocol.PrincipalStore` Protocol.
- [ ] `backend/drive_workspace/tests/` contains the three test modules
      above and `pytest` runs green against SQLite.
- [ ] With `docker compose up -d postgres` and
      `DRIVE_WS_POSTGRES_URL=postgresql+psycopg://dev:dev@localhost:5432/dev
      pytest`, the postgres-gated test class also passes.
- [ ] `ruff check .` and `mypy --strict drive_workspace/` are clean.
- [ ] CI workflow no longer treats exit 5 as success.
- [ ] `docs/plan.md`: tasks 2.2, 2.6, 2.7 marked done; tasks 2.3, 2.4,
      2.5, 2.9 stay "not started" (pending ADR-0008).
- [ ] One commit per logical chunk (Authenticator, SqlAlchemyPrincipalStore,
      LogSchema + reference impl, CI tweak). Final commit references this
      brief filename.

## Notes / open questions

1. **SQLAlchemy session lifecycle**: store takes a `sessionmaker` and
   opens its own session per call (simpler), or takes a `Session` and
   trusts the caller's unit-of-work? Recommendation: `sessionmaker` —
   matches the architecture's stance that the package owns its
   persistence concern within a request.
2. **Where do `Principal` table columns live in the Protocol?** They
   shouldn't — `PrincipalStore` Protocol stays opaque
   (string-keyed input, dict-shaped output). The SQLAlchemy `Principal`
   model is an implementation detail of the default impl.
3. **Postgres test gating**: env-var-driven (recommended) keeps the
   default `pytest` invocation Docker-free. Alternative is a `pytest`
   marker (`@pytest.mark.postgres`) skipped by default. Either works;
   surface the choice in the first commit message.
4. **`google-auth` library version pin**: pyproject already declares
   `google-auth>=2.30`. Confirm `Credentials.from_service_account_file`
   is stable across that range; pin upper bound only if a CVE or API
   break shows up.

## Outcome

Phase 2A landed in five commits on branch `claude/elegant-lewin-aec701`:

1. **`feat(auth): FileAuthenticator default impl + tests`** —
   `backend/drive_workspace/auth.py` with module-level `SCOPES =
   ("…/auth/drive", "…/auth/spreadsheets")`, commented for why each is
   needed. `FileAuthenticator(key_path)` resolves and existence-checks
   the path at construction (fail-fast on misconfigured deploys);
   `credential()` delegates to
   `Credentials.from_service_account_file(..., scopes=list(SCOPES))`.
   Tests mock `from_service_account_file` so they don't need a real RSA
   key; structural Protocol compatibility against
   `workspace.Authenticator` is asserted.
2. **`feat(stores): default SqlAlchemyPrincipalStore + tests`** —
   `backend/drive_workspace/stores/sqlalchemy.py` with
   `Base(DeclarativeBase)`, `Principal` model (`principal_id` PK,
   `folder_id`, `spreadsheet_id`, `display_name?`, `granted_email?`,
   `provisioned_at`, `revoked_at?`), `create_all(engine)` helper, and
   `SqlAlchemyPrincipalStore(sessionmaker[Session])`. Store opens its
   own short-lived session per call. `record_provisioned` is idempotent
   (re-provision refreshes ids and clears `revoked_at`).
   `record_revoked` no-ops on unknown principals. Always-on SQLite
   tests cover the full Protocol surface (provision, idempotent
   re-provision, revoke, revoke-then-reprovision, multi-principal
   isolation, no-op revoke). Postgres-backed test class is gated by the
   `DRIVE_WS_POSTGRES_URL` env var (skipped by default — keeps the
   plain `pytest` invocation Docker-free).
3. **`feat(logs): formalize LogSchema Protocol with ColumnSpec + reference impl`** —
   `ColumnSpec(key, header)` value object; `LogSchema.columns()` now
   returns `list[ColumnSpec]` (was `list[str]`); `render_row` invariant
   is "same length and order as columns()". `ExampleLogSchema`
   (timestamp + principal_id + note + photo_link) lives under
   `tests/_fixtures/example_log_schema.py` so it does not pollute the
   package's importable surface. `__init__.py` re-exports `ColumnSpec`,
   `LogSchema`, and `FileAuthenticator`. `SpreadsheetLogger.append`
   still raises `NotImplementedError("Phase 2B")`.
4. **`ci: drop exit-5 pytest workaround now that real tests exist`** —
   `.github/workflows/backend-ci.yml` Pytest step is now a plain
   `pytest`.
5. **`docs(phase-2a): close session brief and mark plan tasks done`** —
   this commit. `plan.md` tasks 2.2 (file-path Authenticator), 2.6
   (CRUD-only, no Alembic), and 2.7 (Protocol + reference impl, no
   Sheets `append` yet) marked done; tasks 2.3, 2.4, 2.5, 2.9 stay
   "not started" pending ADR-0008.

### Decisions taken inline (per brief's open questions)

- **N1 — session lifecycle**: store takes a `sessionmaker[Session]` and
  opens its own session per call. Matches the brief's recommendation.
- **N2 — Principal columns vs. Protocol**: `PrincipalStore` Protocol
  stays opaque; the SQLAlchemy `Principal` model is an impl detail.
  `display_name` and `granted_email` ship nullable for now since the
  current Protocol does not carry them — a future session can widen
  the Protocol when `FolderManager.provision()` lands.
- **N3 — Postgres test gating**: env-var-driven via
  `DRIVE_WS_POSTGRES_URL`. Default `pytest` requires no Docker.
- **N4 — google-auth pin**: kept at `>=2.30` with no upper bound.

### Verified

- `python -m ruff check drive_workspace/` — clean.
- `python -m mypy --strict drive_workspace/` — clean (18 source files).
- `python -m pytest drive_workspace/tests/` — 17 passed, 1 skipped
  (the postgres class). Postgres class was not run in this session;
  Docker Desktop install on the dev box is still deferred from Phase 1.
  Re-running with `docker compose up -d postgres` and
  `DRIVE_WS_POSTGRES_URL=postgresql+psycopg://dev:dev@localhost:5432/dev`
  exercises the same `_store_contract` path against real Postgres.
- Reference Flask server unchanged: Phase 1 stub endpoints still serve
  per the brief's "Out of scope" list.

### Not verified by this session

- **Postgres-backed store tests**. Docker-gated; not run here. Code
  path is identical to the verified SQLite path apart from the engine
  URL and the `DROP TABLE IF EXISTS` setup/teardown around
  `Base.metadata.create_all`.
- **CI run on GitHub Actions**. The workflow change is a strict
  simplification (drop the exit-5 swallow); locally everything is
  green.

### Notes for the next session (Phase 2B)

- ADR-0008 (test Workspace ownership) needs to land before
  `FolderManager.provision`, `UploadSessionMint.initiate`, or
  `SpreadsheetLogger.append` get real implementations.
- When `FolderManager.provision` lands and starts persisting
  `display_name` + `granted_email`, widen the `PrincipalStore`
  Protocol's `record_provisioned` signature in the same session — the
  default impl's columns are already there, but no other impl can
  populate them through the Protocol surface today.
- ADR-0010 (library dispatcher discipline) does not gate Phase 2A but
  must be resolved before any session that touches
  `DriveUploaderImpl`.
