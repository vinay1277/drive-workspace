# ADR-0011: Resolve SA storage-quota failure with a Shared Drive

- **Status**: accepted
- **Date**: 2026-04-29
- **Supersedes**: —

## Context

The Path B test bed (see `docs/deployment.md`) surfaced a hard failure
that blocks Phase 2B: when the service account calls
`drive.files.create()` to create a file (folders are fine — they are
metadata-only and consume no storage), Google charges the new file's
storage to the SA's own Drive quota. A service account has zero Drive
quota by default. Result: `403 storageQuotaExceeded` even when the
parent folder is owned by a real user. `bootstrap_test_workspace.py`
created the folder topology successfully but had to skip
template-spreadsheet creation for exactly this reason.

Three workarounds exist: (1) put the content in a Shared Drive so files
are charged to the org's pooled storage, (2) use Domain-Wide Delegation
so the SA impersonates a real Workspace user and files are charged to
that user, or (3) some hybrid. The choice affects ADR-0001 (backend-
mediated uploads — credential model), ADR-0002 (per-principal folders,
org-owned), and the shape of `FileAuthenticator`. The maintainer's
Workspace plan (`meternnj-org`, Business Standard+) includes Shared
Drives, so all three options are mechanically available.

## Decision

All `drive-workspace` Drive content — `Master/`, `Templates/`,
`Principals/` and every per-principal subtree — lives inside a single
**Shared Drive** owned by `meternnj-org`. The service account is added
as a **Content Manager** member of that Shared Drive. Files the SA
creates inside the Shared Drive are charged to the org's pooled
storage, not to the SA's (zero) personal quota; the
`storageQuotaExceeded` failure goes away.

The library code path is otherwise unchanged: `FileAuthenticator` keeps
its current signature; ADR-0001's "credentials never on the device"
property holds; ADR-0002's "org-owned, view-only share with the
principal" model is satisfied natively (Shared Drive items are
org-owned by definition, and items inside a Shared Drive can be shared
with external emails on a per-item basis).

Phase 2B implementation must pass `supportsAllDrives=True` and
`includeItemsFromAllDrives=True` on every Drive API call that touches
Shared-Drive content (see Implementation notes).

## Consequences

**Positive**:
- Resolves the failure with **zero library auth-code change**.
  `FileAuthenticator` stays as-is; no `subject=` plumbing, no
  Credentials-with-subject branch, no new test surface, no migration
  for hosts that already construct `FileAuthenticator(key_path)`.
- ADR-0002's "org owns every byte from creation" is satisfied
  structurally, not by convention. Shared Drive membership and item
  ownership are decoupled from any individual user account, so there
  is no "what happens when user X leaves" question for any file the
  library writes.
- Smallest possible blast radius if the SA key leaks. Attacker sees
  the contents of one Shared Drive — the test bed's own data — and
  cannot impersonate Workspace users elsewhere in the org, cannot
  reach personal Drives, cannot reach other Shared Drives the SA is
  not a member of. (DWD's leak surface is the entire set of users the
  delegation grants the SA permission to act-as, which is org-wide
  for any practical scope.)
- Operationally simpler. SA membership is one Shared Drive
  setting, managed alongside the Shared Drive itself. No
  admin-console "API client access" scope grants per SA per scope.
  Rotation is unchanged from today: rotate the SA key; membership
  follows the SA email.
- Annual scope review (ADR-0008) becomes "is the SA still a member of
  exactly the test Shared Drive, with `drive` + `spreadsheets`
  scopes?" — checkable in two clicks.

**Negative**:
- Drive API calls must include the `supportsAllDrives` and
  `includeItemsFromAllDrives` flags, or the call returns 404 / "file
  not found" for items that exist but are inside a Shared Drive. This
  is a Phase 2B implementation discipline (see flag checklist below)
  and is enforced by the integration tests in Phase 3.
- Per-item shares to external emails (the principal's view-only
  share) work but inherit the Shared Drive's external-sharing policy.
  If `meternnj-org` ever sets the Shared Drive to "members of the org
  only", the per-principal share to a personal Gmail breaks. This is
  a Workspace admin policy choice that lives outside the codebase;
  documenting it here so a future admin who tightens external
  sharing knows what they will break.
- Locks the test bed (and Phase 4 production) to a Workspace plan
  tier that includes Shared Drives. Business Standard+ today; if the
  org ever downgrades to Workspace Starter or migrates back to
  personal Gmail, this ADR must be revisited and DWD becomes the
  fallback.

**Rejected alternatives**:

- *Domain-Wide Delegation (DWD).* Works on any Workspace plan. Adds a
  `subject` parameter to `FileAuthenticator` and an admin-console
  scope grant per SA per OAuth scope. Larger blast radius than
  Shared Drives: a leaked DWD-enabled SA key plus the granted scopes
  lets the attacker `act-as` any user across the org, not just one
  Shared Drive's contents. Per-user file attribution would be the
  one DWD-only benefit, but ADR-0002 puts attribution in
  `PrincipalStore`, not in Drive's `owner` field; we do not need
  DWD's attribution. Documented as a fallback if the Shared Drives
  prerequisite ever fails.
- *Hybrid (Shared Drive for `Master/Templates`, DWD for
  `Principals`).* Adds DWD's complexity and blast-radius cost
  without a benefit Shared Drives alone do not already provide for
  the per-principal case (per-item external share works inside a
  Shared Drive). Worth reconsidering only if a future requirement
  surfaces that genuinely needs per-principal Drive ownership — at
  which point a superseding ADR is appropriate.
- *Leave the SA unchanged.* This is the failure we observed.
  `bootstrap_test_workspace.py` cannot create the template
  Spreadsheet; `FolderManager.provision`, `UploadSessionMint.initiate`
  (which creates a placeholder Drive file before opening the
  resumable session), and `SpreadsheetLogger.append` (Sheet rows are
  fine, but the Sheet itself was created by the SA) all fail
  `403 storageQuotaExceeded` in Phase 2B. Listed for completeness;
  not a viable path forward.
- *Per-user OAuth on the device, replacing the SA path.*
  Contradicts ADR-0001 (no Drive credentials on the device). Adds
  per-seat Workspace cost. Reintroduces a long-lived Drive
  credential on each device. Out of scope.

## Implementation notes

### Test-bed migration (Path A continuation)

When `drive-workspace-test-494511` clears Google's account
verification (see `docs/deployment.md` "Path A migration plan"), the
provisioning checklist gains these steps:

1. In `meternnj-org` admin console, create a **Shared Drive** named
   `drive-workspace-test`.
2. Set the Shared Drive's external-sharing policy to **allow members
   outside the organization** (required so per-principal view-only
   shares to personal-Gmail principals work). If the org has a
   contradicting policy, this ADR's per-principal share story breaks
   and the affected operations need an explicit Workspace exception.
3. Add `drive-workspace-test-sa@drive-workspace-test-494511.iam.gserviceaccount.com`
   as a **Content Manager** of the Shared Drive. (Manager is too
   permissive: it allows the SA to delete the Shared Drive itself
   and modify membership. Content Manager allows file/folder
   create/edit/delete inside the drive, which is the actual
   permission set we want.)
4. Re-run a Shared-Drive-aware variant of
   `backend/.secrets/bootstrap_test_workspace.py`: same folder
   topology, but parented inside the Shared Drive root, with every
   API call carrying `supportsAllDrives=True`. The Sheet creation
   step that `403`'d on Path B will succeed.
5. Capture the new Shared Drive ID and the recreated folder IDs in
   `docs/deployment.md` (replacing the Path B IDs).

The bootstrap script does not need to be re-run against the current
Path B SA before this migration; Path B is acknowledged-blocked on
the Sheet-creation step and the smoke test does not depend on a
Sheet existing.

### Env / config that Phase 2B will touch

| Variable                              | Purpose                                                     |
|---------------------------------------|-------------------------------------------------------------|
| `DRIVE_WORKSPACE_SHARED_DRIVE_ID`     | New. The Shared Drive ID. Required by `FolderManager` and `UploadSessionMint`. Constructor rejects empty string at startup. |
| `DRIVE_WORKSPACE_ROOT_FOLDER_ID`      | Existing. Now refers to a folder *inside* the Shared Drive (the `drive-workspace-test/` root in Path B becomes a sub-folder of the Shared Drive in Path A). Stays as the practical "where do principals live" handle. |
| `DRIVE_WORKSPACE_SA_KEY_PATH`         | Existing. Unchanged.                                        |

`FileAuthenticator` is **not modified by this ADR.** Its signature,
scopes, and tests remain as they are today.

### Shared Drives flag checklist for Phase 2B

Every Drive API call that the library makes must carry both flags
unless the call's documented behaviour explicitly says otherwise.
Phase 2B and Phase 3 integration tests are the enforcement points;
this checklist lives in this ADR so the reviewer can spot omissions
during code review.

| Operation                                              | `supportsAllDrives` | `includeItemsFromAllDrives` |
|--------------------------------------------------------|---------------------|-----------------------------|
| `drive.files.create` (folder, file, copy, spreadsheet) | ✅ required         | n/a                         |
| `drive.files.copy` (template → per-principal folder)   | ✅ required         | n/a                         |
| `drive.files.get` (lookup by ID)                       | ✅ required         | n/a                         |
| `drive.files.list` (search/list inside the Shared Drive) | ✅ required       | ✅ required                 |
| `drive.permissions.create` (view-only share with principal) | ✅ required    | n/a                         |
| `drive.permissions.list` / `delete` (offboarding revoke) | ✅ required       | n/a                         |
| Resumable-session mint (`POST /upload/drive/v3/files?uploadType=resumable`) | ✅ required as `supportsAllDrives=true` query param | n/a |
| Sheets API (`spreadsheets.values.append` etc.)         | n/a (Sheets API is not Shared-Drive-aware in the same way; the spreadsheet's location is determined at creation time in Drive) | n/a |

`google-api-python-client` exposes these as kwargs on the relevant
`.list()`, `.get()`, `.create()`, `.copy()`, `.delete()` methods on
`drive_service.files()` and `drive_service.permissions()`. Setting
them globally is not possible; each call site must pass them.

### Phase 4 (SmartMeter integration) implication

The Phase 4 production target inherits this decision: SmartMeter's
`drive-workspace` deployment lives inside its own production Shared
Drive in the SmartMeter Workspace tenant, with a dedicated production
SA as Content Manager. The library code is identical to the test
deployment; only `DRIVE_WORKSPACE_SHARED_DRIVE_ID` and
`DRIVE_WORKSPACE_ROOT_FOLDER_ID` differ.

### When to revisit this ADR

- The Workspace plan drops below Business Standard (Shared Drives no
  longer available).
- A workflow surfaces that genuinely requires per-principal Drive
  ownership (would supersede ADR-0002 first, then this).
- A future Drive API change makes `supportsAllDrives=True` no longer
  necessary or no longer sufficient.

This ADR was written without re-running the bootstrap script; the
Phase 2B integration tests in Phase 3 are the first executable proof
that the chosen approach works end-to-end. Path A migration is the
operational gate that turns this from a paper decision into a running
test bed.
