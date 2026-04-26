# Deployment Configuration

> Operational record of how the test bed is provisioned. Update when
> anything in here changes. Companion to [ADR-0008](decisions/0008-test-workspace-ownership.md)
> (test Workspace ownership) and [ADR-0006](decisions/0006-stack-choices.md)
> (secrets management).

---

## Current state — Path B (temporary)

Phase 2 was supposed to begin with the test Workspace at `meternnj-org` per
ADR-0008, but the GCP project `drive-workspace-test-494511` (which we did
create under that org) is held in **account verification review** by Google
— pending APIs cannot be enabled until the review clears, which Google
warns may take "a few days."

To unblock smoke-testing of `drive_workspace`, we adopted a temporary
arrangement we call **Path B**: reuse the existing `vision-ocr` service
account from a *different* GCP project that's already verified, and a Drive
folder we created in `meternnj@gmail.com`'s personal Drive (under
`meternnj-org`).

This is a known deviation from ADR-0008. **Path A migration plan** is below.

### Path B — what's wired up today

| Item                               | Value                                                                  |
|------------------------------------|------------------------------------------------------------------------|
| Workspace org                      | `meternnj-org`                                                         |
| GCP project (where SA lives)       | `gen-lang-client-0007734483` (under `jpss1277@gmail.com`'s SmartMeter project) |
| GCP project (intended, parked)     | `drive-workspace-test-494511` (under `meternnj-org`, verification pending) |
| Service account email              | `vision-ocr@gen-lang-client-0007734483.iam.gserviceaccount.com`        |
| OAuth scopes granted               | `drive`, `spreadsheets` (the SA was originally minted for Vision OCR; we reuse it) |
| Local SA key path                  | `backend/.secrets/dev-sa.json` (gitignored)                            |
| CI secret name                     | not yet uploaded (Path B is local-only)                                |
| Drive root folder                  | `/drive-workspace-test/` in `meternnj@gmail.com`'s My Drive            |

### Drive folder topology (created 2026-04-26)

All folder IDs were minted by the SA via Drive API and recorded by
[`backend/.secrets/bootstrap_test_workspace.py`](../backend/.secrets/bootstrap_test_workspace.py)
(gitignored, captures real IDs).

```
drive-workspace-test                               1OIT3r4FmaREHzVsoy6bP2s24S83nFvEk
├── Master                                         11V8WzpALYyZCznydIahn2Lu2TILT13Rd
├── Templates                                      1GrbYw7vIwRI1P4ZGq-bz873DODM4dvn2
│   └── PrincipalFolderTemplate                    1LQ_SdVY3kRM5ssT4zJeY71mlSJhtR_pg
│       ├── photos                                 194hQPZCa-0E-8FFFZRCWMTlU5R-faWYi
│       ├── audio                                  1UCKcieMo1qByIj3aQ2PqbI59fcoOGfQK
│       └── videos                                 1cZw2R8Nb0RPQGd60aW34j4WVmgmQBfSv
└── Principals                                     1QFDTCxVFT2Vmy4dZmloG7AhxnANAYPxI
```

Root folder shared with the SA email as Editor. Sub-tree was created by the
SA via the bootstrap script.

### Env vars the reference server reads (when wired)

| Var                                   | Purpose                                |
|---------------------------------------|----------------------------------------|
| `DRIVE_WORKSPACE_SA_KEY_PATH`         | `backend/.secrets/dev-sa.json`         |
| `DRIVE_WORKSPACE_ROOT_FOLDER_ID`      | `1OIT3r4FmaREHzVsoy6bP2s24S83nFvEk`    |

---

## Path B — known limitations (won't survive Phase 2B as-is)

These are SA-quota and SA-credential issues that the smoke test surfaced.
They are tolerable for a smoke test against a single shared folder; they
will require resolution before Phase 2B can ship real provisioning.

1. **Service-account file creation is rate-limited by SA's own (zero)
   Drive storage quota.** When the SA creates a new file via
   `drive.files.create()`, even with `parents=[user_owned_folder_id]`,
   Google charges the storage to the SA, not the parent's owner. Result:
   `403 storageQuotaExceeded` for any file the SA creates from scratch.
   The bootstrap script creates folders successfully (folders count as
   metadata-only, no quota) but cannot create the template Spreadsheet —
   that step is deliberately skipped.

   **Fixes for Phase 2B (pick one):**
   - **Shared Drives** (formerly Team Drives) — files in Shared Drives count
     against the org's pooled quota, not any individual SA. Requires a
     Workspace plan that includes Shared Drives.
   - **Domain-wide delegation** — SA impersonates a real Workspace user;
     created files belong to that user. Requires Workspace admin to grant
     the SA delegation rights for specific scopes.
   - **Pre-created files** — a real user creates files in advance, SA
     mutates them. Doesn't scale to per-principal provisioning.

2. **Vision-OCR-named SA serving multiple purposes.** The SA's name is
   misleading — `vision-ocr` is now also the drive-workspace-test bed SA.
   Acceptable for a temporary arrangement; not for production.

3. **No CI key.** Path B is local-development only. CI runs cannot use this
   SA without uploading a CI-distinct key, which we haven't done because
   the whole arrangement is temporary.

4. **Operational comingling.** The SA shares quota and audit space with
   whatever else `gen-lang-client-0007734483` is doing (vision OCR,
   probably). A misbehaving test could in theory affect that workload's
   visible quota dashboards.

---

## Path A migration plan (target state per ADR-0008)

When `drive-workspace-test-494511` (under `meternnj-org`) clears Google's
account-verification review:

1. **Enable Drive + Sheets APIs** in `drive-workspace-test-494511`.
2. **Create a dedicated SA** named `drive-workspace-test-sa@drive-workspace-test-494511.iam.gserviceaccount.com`.
3. **Generate two distinct keys:**
   - Local: `backend/.secrets/dev-sa.json` — *replaces* the current
     `vision-ocr` key.
   - CI: GitHub Actions secret `DRIVE_WORKSPACE_TEST_SA_KEY`.
4. **Re-share the existing Drive folder topology** (or move it) with the new SA.
   Drop the share with `vision-ocr@...`. The folder IDs stay the same;
   only the access-control row changes.
5. **Decide on the Path-B-known-limitation #1 fix** (Shared Drive vs. DWD)
   and provision that infrastructure.
6. **Re-run the bootstrap script** against the new SA; expected: folders
   already exist (idempotent), Sheet creation now succeeds (because
   Shared Drive / DWD).
7. **Update this document**:
   - Replace the Path B section with a "Path A — current" section.
   - Move Path B notes to a "History — superseded" section.
   - Set the annual-scope-review calendar reminder per ADR-0008
     Implementation notes.
8. **Rotate** the `vision-ocr` key — even though we used it briefly, treat
   it as touched and have the SA's owner rotate it.

Estimated effort: 30 min once verification clears.

---

## Annual review (per ADR-0008)

> Ignore until Path A is live; not applicable to Path B since the SA is
> shared with another workload.

- [ ] **YYYY-MM-DD**: confirmed SA still has only `drive` + `spreadsheets` scopes
- [ ] **YYYY-MM-DD**: confirmed no shares to the SA outside the test root folder

---

## Rotation log

| Date       | What rotated                        | Reason                                         |
|------------|-------------------------------------|------------------------------------------------|
| 2026-04-26 | Path B initial provision (no rotation; SA reused from existing project) | Drive workspace bootstrap blocked on Google account verification |

---

## Operational notes

### 2026-04-26 — Docker Desktop installed; `docker compose up` verified

Docker Desktop was previously deferred (see `plan.md` Phase 1 status — Phase 1
verification ran via `flask run` directly). It is now installed on the dev
box and the full compose stack boots clean:

| Component                       | Status |
|---------------------------------|--------|
| `docker version` (client)       | 29.4.0 |
| `docker compose version`        | v5.1.2 |
| `postgres` container            | healthy on `:5432` |
| `reference_server` container    | up on `:8080` |
| `GET http://localhost:8080/health` | `{"status":"ok"}` |

Install hiccup worth recording: a leftover `C:\ProgramData\DockerDesktop`
directory from a previous partial install was owned by the regular user
and the installer refused to proceed ("must be owned by an elevated
account"). Fix was to `takeown /F /R /D Y` + `icacls /grant
Administrators:(OI)(CI)F /T` + `rmdir /S /Q` from an elevated cmd, then
re-run the installer. WSL2 backend; `--accept-license` non-interactive
install.

### Tags landed locally (not yet pushed — no remote configured)

| Tag                     | Commit    | Meaning                                          |
|-------------------------|-----------|--------------------------------------------------|
| `phase-1-complete`      | `f2d5284` | Phase 1 skeleton + ADR-0008/9 + bug-fix merge    |
| `phase-2a-complete`     | `9931cbc` | Phase 2A merge (protocols, FileAuth, stores, LogSchema) |
| `adr-0010-applied`      | `c65b49c` | ADR-0010 implementation merge                    |
| `path-b-bootstrapped`   | `0d67ec1` | This document — Path B deployment record         |

### Open: no git remote yet

`git remote -v` is empty. Tags and commits are local-only until a GitHub
repo URL is provided and `git remote add origin <url> && git push -u
origin main && git push origin --tags` runs. **Next session should
either**: (a) create the GitHub repo and push, or (b) explicitly accept
local-only as the steady state and remove this note.
