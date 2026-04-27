# Session: 2026-05-06 — Phase 3.1: package unit tests with `responses`

> **Test-only session.** Land `responses`-backed unit tests for the
> entire `drive_workspace` public surface. Today the package has tests
> for `auth`, `stores`, `logs`, and `migrations` — all the parts that
> don't make HTTP calls. The HTTP-touching parts (`folders`, `uploads`,
> `logs.SpreadsheetLogger`, `reconcile`) currently raise
> `NotImplementedError("Phase 2B")`. Phase 2B will write the real
> implementations; **this session writes the tests they must pass.**

## Goal

By end of session: `pytest --cov=drive_workspace backend/` reports
**≥85% line coverage on `drive_workspace/`** (per the maturity checklist).
All HTTP-touching paths have unit tests using `responses` to mock the
Drive and Sheets REST APIs — happy path plus the error responses each
operation must handle. Every test runs offline; the suite must pass
with `pytest --offline` if the maintainer ever adds that flag.

The tests are **specifications for Phase 2B implementations.** They
will fail today (Phase 2B code raises `NotImplementedError`) and that
is expected. Skip them with `pytest.mark.skip(reason="Phase 2B")` so
the suite stays green; remove the skips one-by-one as Phase 2B lands
each operation.

## Required reading (before writing code)

- `docs/plan.md` Phase 3.1 (the maturity gate this session closes)
- `docs/decisions/0011-sa-storage-quota.md` (Shared Drives requirement —
  every Drive API call mock must include `supportsAllDrives=True`)
- `docs/decisions/0002-per-principal-folders-org-owned.md` (folder
  lifecycle tests — provision, view-only share, revoke)
- `docs/decisions/0003-session-prefetch-bank.md` (initiate-upload
  with `count` parameter; tests exercise both `count=1` and `count=N`)
- `backend/drive_workspace/folders.py`, `uploads.py`, `logs.py`,
  `reconcile.py` — modules under test
- `backend/drive_workspace/tests/test_sqlalchemy_store.py` — the
  established test pattern (pytest fixtures, naming, structure)
- `backend/reference_server/tests/test_stub_upload.py` — the resumable
  upload state machine reference; tests here mock the same wire
  protocol but at the Drive-API client layer
- The `responses` library docs: <https://github.com/getsentry/responses>

Do not read prior session transcripts.

## In scope

### `backend/drive_workspace/tests/test_folders.py` — new file

Mocks Drive REST API. Tests `FolderManager.provision` and `revoke`:

- **provision happy path**: `files.copy` of template folder + `permissions.create`
  with `role=reader` for the principal's email + `principal_store.record_provisioned`
  with the new ids. Mock both the Drive copy response and the permission
  creation; assert the one outbound HTTP call shape per Drive op.
- **provision idempotency**: re-provisioning an already-provisioned principal
  refreshes ids and clears `revoked_at` (matches the store's contract).
- **provision: SA cannot copy template**: 403 from `files.copy` propagates
  as a clean exception (not raw `googleapiclient.HttpError`).
- **provision: principal store write fails**: rolls back the Drive folder
  creation? Or accepts the orphan and lets reconciliation clean up?
  Recommend the latter (matches `bootstrap_test_workspace.py` pattern);
  document the choice in the test docstring and ADR-0002 if it isn't there.
- **revoke happy path**: drops the `permissions.delete` for the principal's
  share + `principal_store.record_revoked`. Files stay (assert no
  `files.delete` call).
- **revoke on already-revoked principal**: no-op (no Drive calls; no
  store mutation).
- **revoke on unknown principal**: no-op + log warning.
- **all calls include `supportsAllDrives=True`** — verify via the
  `responses` call captures.

### `backend/drive_workspace/tests/test_uploads.py` — new file

Mocks Drive REST API. Tests `UploadSessionMint.initiate`:

- **single-session happy path**: `count=1` → POST to
  `/upload/drive/v3/files?uploadType=resumable` returns 200 with
  `Location:` header → returned `UploadSession` carries that URL +
  `drive_file_id` from the response body.
- **batched happy path**: `count=10` → 10 sequential resumable-session
  creations → returns `list[UploadSession]` of length 10. Verify the
  10 Drive API calls were actually made; verify each session has a
  unique `drive_file_id`.
- **count exceeds `MAX_PREFETCH_COUNT`**: raises `ValueError`
  before any HTTP call.
- **count is 0 or negative**: raises `ValueError`.
- **Drive returns 5xx**: propagates as an exception; no partial state
  in the audit log.
- **audit row written for each minted session**: per the Path A
  migration plan in deployment.md; assert the `principal_store` audit
  hook gets called (count=N → N audit calls).
- **`shared_drive_id` propagates** to the Drive metadata: every
  `files.create` call includes the right `parents` (the principal's
  per-folder id, which lives inside the Shared Drive).

### `backend/drive_workspace/tests/test_spreadsheet_logger.py` — new file

Mocks Sheets REST API. Tests `SpreadsheetLogger.append`:

- **happy path**: lookup `spreadsheet_id` via `principal_store` →
  Sheets `values.append` with the rendered row → returns silently.
- **principal not provisioned**: `get_spreadsheet_id` returns `None` →
  `LogSchemaError` (or whatever name we settle on; coordinate with
  Phase 2B impl session).
- **revoked principal**: same as not-provisioned — silently rejects.
- **Sheets API 429**: retries (or doesn't?) — pin the policy in this
  session, document the choice.
- **payload missing required keys**: depends on host's TypedDict
  rigor; the package's contract is "render whatever the host gives
  us." Test that `render_row` is called once per `append`, with the
  payload as-is.
- **append uses `valueInputOption=USER_ENTERED`** so HYPERLINK
  formulas evaluate, not appear as literal text.

### `backend/drive_workspace/tests/test_reconcile.py` — new file

Mocks Drive REST API. Tests `ReconciliationRunner.run`:

- **no orphans**: empty audit table → no Drive calls → returns
  empty `ReconciliationReport`.
- **single orphan**: audit row in `pending` state, > 24h old → check
  the `drive_file_id` on Drive (`files.get`) → if the file has 0
  bytes (or doesn't exist), mark the audit row `abandoned`.
- **single completed-but-not-committed**: audit row `pending`, file
  has bytes but no host survey row references it. Per Phase 4
  intent, mark `orphaned`; do NOT delete the Drive file in this
  session — production CLI gets a `--delete` flag, default off.
- **dry-run mode**: `run(dry_run=True)` returns a report listing
  what *would* change without writing.
- **`python -m drive_workspace.reconcile` CLI smoke**: the CLI
  parses `--older-than 24h` and `--dry-run`, calls the runner.

### `backend/drive_workspace/tests/conftest.py` — new file (or extension)

- Shared `responses` activation fixture per test (auto-use).
- Fake `principal_store` factory — generic `MagicMock` satisfying the
  `PrincipalStore` Protocol; tests configure it per-method.
- Fake `LogSchema` factory — same pattern.
- A `DriveWorkspace` builder fixture wiring the above with a
  `FileAuthenticator` that points at a fixture SA key file (the same
  fake key used by `test_auth.py`).
- A `shared_drive_id="0AB..."` constant the tests use uniformly so
  every `responses` matcher can include it.

## Out of scope

- Real Drive or Sheets API calls. This is `responses`-only. Phase
  3.2 covers integration tests against real APIs.
- Implementing the actual Phase 2B code paths. This session writes
  the tests; the impl session deletes the `pytest.mark.skip` one
  by one.
- Concurrency tests against the audit table. Phase 3 separately.
- Coverage tooling configuration (jacoco-style threshold gate in
  CI). Phase 3 separately.

## Definition of done

- [ ] Four new test modules listed above exist and contain at least
      the tests enumerated.
- [ ] Each test that exercises a `NotImplementedError("Phase 2B")`
      method is decorated with `@pytest.mark.skip(reason="Phase 2B")`
      so the suite stays green today.
- [ ] `pytest --cov=drive_workspace backend/` reports `≥85%` line
      coverage on `drive_workspace/` (the skipped tests still count
      against the import; the lines that *can* be exercised now —
      auth, stores, logs Protocol, migrations, the new conftest
      fixtures — must be ≥85% covered without the skips counting).
- [ ] `mypy --strict drive_workspace/` and the test files pass.
      Tests should be `from __future__ import annotations` and
      typed.
- [ ] `ruff check .` clean.
- [ ] `sphinx-build -W` still passes (no docstring rot).
- [ ] One commit. Message references this brief filename.

## Notes / open questions

1. **Skip-then-unskip discipline**: when Phase 2B lands a real
   `FolderManager.provision`, that session's commit removes the
   `@pytest.mark.skip` from the corresponding test and asserts the
   test now passes. This is the contract-test pattern — the test
   is the spec. Document it in the new conftest's module docstring.
2. **Coverage of skipped paths**: a `# pragma: no cover` on the
   `raise NotImplementedError(...)` lines in `folders.py` /
   `uploads.py` / etc. lets the 85% target be met without lying.
   Add them in this session.
3. **Error-type design**: the tests above reference exceptions like
   `LogSchemaError` that don't exist yet. This session can either
   (a) define them as sub-classes of a `DriveWorkspaceError` base
   in `drive_workspace/errors.py`, or (b) defer and use plain
   `RuntimeError` in tests, then refine in Phase 2B. Recommend (a)
   — write the error hierarchy now since the tests need it; Phase
   2B raises them.
4. **`responses` vs. `requests-mock`**: `responses` is in the
   `[dev]` deps already. Stick with it.
5. **Audit table**: the tests assume an audit table; the
   `SqlAlchemyPrincipalStore` doesn't have one yet (Phase 2A only
   shipped the principals table). This session adds an audit table
   to the SQLAlchemy default impl, or defers to a follow-up. **Recommend
   defer** — add a new task to plan.md for "Phase 2B prereq: audit
   table on `SqlAlchemyPrincipalStore`" and have the reconcile
   tests use a `MagicMock` audit hook in the meantime.

## Outcome

> Filled in at end of session.

(blank — to be completed)
