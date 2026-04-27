# Deployment Configuration

> Operational record of how the test bed is provisioned. Update when
> anything in here changes. Companion to [ADR-0008](decisions/0008-test-workspace-ownership.md)
> (test Workspace ownership) and [ADR-0006](decisions/0006-stack-choices.md)
> (secrets management).

---

## Current state — Path B 2.0 (Shared Drive on a real Workspace)

Phase 2 was supposed to begin with the test Workspace at the GCP project
`drive-workspace-test-494511` (under what looked like `meternnj-org` in
GCP), per ADR-0008. That project remains held in Google **account
verification review** with no clear ETA. Investigation revealed a deeper
issue: `meternnj-org` was a Cloud Identity Free organization, not a real
Google Workspace — so even when verification eventually clears, the path
to ADR-0011's required Shared Drives is more complicated than originally
modeled.

We resolved both blockers in one move on 2026-04-27:

1. **Subscribed to Google Workspace Business Standard** for `meternnj.com`
   (~$12/user/mo, 14-day trial then billing). This created a real
   Workspace tenant titled "J P Saftek Systems" with admin user
   `jpss1277@meternnj.com` and unlocked Shared Drives.
2. **Provisioned a Shared Drive** `drive-workspace-test-shared`
   (id `0AK3REUur29BiUk9PVA`) under that Workspace.
3. **Added the existing `vision-ocr` SA as Content Manager** on the Shared
   Drive. External-share warning accepted (the SA lives in a different
   GCP project `gen-lang-client-0007734483` — ADR-0011 explicitly
   anticipated this in its sharing-policy requirement).
4. **Re-bootstrapped the folder topology** inside the Shared Drive via
   `bootstrap_test_workspace.py`. Every API call passes
   `supportsAllDrives=True` per ADR-0011. Crucially, **Sheet creation
   succeeded** — the SA-quota wall that blocked Path B 1.0 is gone
   because Shared Drive content charges to the org's pooled storage.

This **is** the live arrangement. ADR-0008's intended target state
(`drive-workspace-test-494511` Workspace project) is now a *future
optional consolidation*, not the next required step.

### Path B 2.0 — what's wired up

| Item                               | Value                                                                  |
|------------------------------------|------------------------------------------------------------------------|
| Workspace tenant                   | "J P Saftek Systems" on `meternnj.com` (Business Standard)             |
| Workspace admin user               | `jpss1277@meternnj.com`                                                |
| GCP project (where SA lives)       | `gen-lang-client-0007734483` (under `jpss1277@gmail.com`'s SmartMeter project) |
| GCP project (intended, parked)     | `drive-workspace-test-494511` (verification still pending)             |
| Service account email              | `vision-ocr@gen-lang-client-0007734483.iam.gserviceaccount.com`        |
| OAuth scopes granted               | `drive`, `spreadsheets`                                                |
| SA membership role                 | **Content Manager** on the Shared Drive (per ADR-0011)                 |
| Local SA key path                  | `backend/.secrets/dev-sa.json` (gitignored)                            |
| CI secret name                     | not yet uploaded (Path B 2.0 is local-only)                            |
| Shared Drive name                  | `drive-workspace-test-shared`                                          |
| Shared Drive ID                    | `0AK3REUur29BiUk9PVA`                                                  |

### Drive folder topology (created 2026-04-27, inside Shared Drive)

All folder IDs were minted by the SA via Drive API with
`supportsAllDrives=True`, recorded by
[`backend/.secrets/bootstrap_test_workspace.py`](../backend/.secrets/bootstrap_test_workspace.py)
(gitignored, captures real IDs).

```
drive-workspace-test-shared                        0AK3REUur29BiUk9PVA   ← Shared Drive root
├── Master                                         1lUnmyAJhGmNiJGgPCQKg-WO-vNO-JdX0
├── Templates                                      1W-CRRbJM0AA8jIcMAMHdTAv_b4BIzXjq
│   └── PrincipalFolderTemplate                    1TZnL89mZXOq0J3J4dtKDduxiBe_dEfrz
│       ├── photos                                 1uS_W23oVhnVCca2JrIPUSf_lbEwCtmco
│       ├── audio                                  1OzdLJeF5zS9skH27a2CwFZiUGMQEY36Z
│       ├── videos                                 1W6QdYhlhf3Fa733pXIuzuWsuftKowfnM
│       └── log.gsheet                             1JqvrRMqN_PWq8Qv7_CFXiGCjsLt8K5XjZj1t6oGyCX4
└── Principals                                     1uunv1L0rse9hMwu7yLfoUe1_CxuFlTTL
```

The folder topology of Path B 1.0 (in `meternnj@gmail.com`'s My Drive,
under the same name `drive-workspace-test`) is **abandoned in place** —
not deleted, not migrated, just orphaned. Phase 2B implementations
target the Shared Drive only.

### Env vars the reference server reads (when wired)

| Var                                       | Purpose                                       |
|-------------------------------------------|-----------------------------------------------|
| `DRIVE_WORKSPACE_SA_KEY_PATH`             | `backend/.secrets/dev-sa.json`                |
| `DRIVE_WORKSPACE_SHARED_DRIVE_ID`         | `0AK3REUur29BiUk9PVA` (per ADR-0011)          |
| `DRIVE_WORKSPACE_ROOT_FOLDER_ID`          | `0AK3REUur29BiUk9PVA` (== Shared Drive root)  |

---

## Path B 2.0 — known limitations

The SA-quota wall (which broke Path B 1.0) is **gone**: Shared Drive
storage charges to the org's pooled quota, not the SA. The remaining
Path B 2.0 limitations are operational, not blocking.

1. ~~**Service-account file creation is rate-limited by SA's own (zero)
   Drive storage quota.**~~ **RESOLVED on 2026-04-27** by adopting
   ADR-0011's Shared Drive flow. Folder + Sheet creation now succeed
   under the org's pooled storage; bootstrap script's Step 5 (Sheet)
   passed cleanly.

2. **Vision-OCR-named SA serving multiple purposes.** The SA's name is
   misleading — `vision-ocr` is now also the drive-workspace-test bed
   SA. Acceptable for a temporary arrangement; not for production.
   Production `drive_workspace` deployments will mint their own
   dedicated SA per host.

3. **No CI key.** Path B 2.0 is still local-development only. CI runs
   cannot use this SA without a separate CI key uploaded as a GitHub
   Actions secret. Path-A migration (or just minting a CI-distinct
   `vision-ocr` key) is the cleanup.

4. **Operational comingling.** The SA shares quota and audit space with
   whatever else `gen-lang-client-0007734483` is doing (vision OCR,
   probably). A misbehaving test could in theory affect that workload's
   visible quota dashboards. Mitigated by the Shared Drive boundary —
   Drive storage now goes to the Workspace pool, not GCP — but API
   quota counters are still per-project.

5. **Domain TXT verification still pending.** The Workspace setup
   wizard requested a `google-site-verification=...` TXT record on
   `meternnj.com` (currently registered at Namecheap). We have the
   value but DNS may not have propagated yet. Workspace functions
   without this completing — Drive, Shared Drives, Sheets, admin
   console all work — but some advanced features (custom domain MX
   for email, domain-level OAuth scopes for client apps) remain
   gated until verification passes.

---

## Path A consolidation (optional, no longer urgent)

Path B 2.0 is fully operational, so the original "Path A migration"
plan changes character: it's no longer the *unblock* path — Path B 2.0
already unblocks everything Phase 2B needs. Path A becomes an *optional
consolidation* if/when Google clears verification on
`drive-workspace-test-494511`.

The simplification: under Path A, **the Shared Drive doesn't move**.
Only the SA changes. Steps when (or if) we choose to do it:

1. **Enable Drive + Sheets APIs** in `drive-workspace-test-494511`
   (assuming verification has cleared).
2. **Create a dedicated SA** named
   `drive-workspace-test-sa@drive-workspace-test-494511.iam.gserviceaccount.com`.
3. **Generate two distinct keys:**
   - Local: `backend/.secrets/dev-sa.json` — *replaces* the current
     `vision-ocr` key.
   - CI: GitHub Actions secret `DRIVE_WORKSPACE_TEST_SA_KEY`.
4. **Add the new SA as Content Manager** on the existing Shared Drive
   `drive-workspace-test-shared` (id `0AK3REUur29BiUk9PVA`). Drop
   `vision-ocr@...` from the membership list. **Folder IDs stay the
   same** — no migration of files needed.
5. **Re-run `bootstrap_test_workspace.py`** with the new SA key — should
   be a no-op (every `ensure_subfolder` finds the existing folder).
6. **Update this document**: rename "Path B 2.0" section to "Path A —
   current"; move the `vision-ocr`-related notes to a "History"
   section.
7. **Rotate** the `vision-ocr` key — production hygiene; the key was
   touched.

Estimated effort: 15 min once verification clears.

**Whether to do this at all** is a judgement call:

- Pros: cleaner separation (dedicated SA per concern, name matches
  purpose, no comingling with vision-OCR workload).
- Cons: migration cost; the working bed is already working.

If verification never clears (which is fine — Path B 2.0 is durable),
this section becomes "Phase 4 follow-up: when SmartMeter hosts production,
provision its own dedicated SA along the same pattern."

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

### 2026-04-29 — Phase 2B prep: ADR-0011 chosen approach

[ADR-0011](decisions/0011-sa-storage-quota.md) closes the SA-quota
question that this document surfaced. **Decision: Shared Drives.** No
library auth-code change in this session; `FileAuthenticator` is
unchanged. Phase 2B picks up the implementation discipline.

**What Phase 2B inherits from this decision:**

| Item                              | Value                                                    |
|-----------------------------------|----------------------------------------------------------|
| New env var                       | `DRIVE_WORKSPACE_SHARED_DRIVE_ID` (constructor-validated, non-empty) |
| Existing env var, new meaning     | `DRIVE_WORKSPACE_ROOT_FOLDER_ID` is now a folder *inside* the Shared Drive |
| Required Drive API kwargs         | `supportsAllDrives=True` (every call) and `includeItemsFromAllDrives=True` (list/search) |
| SA role on the Shared Drive       | Content Manager (not Manager — Manager is too permissive) |
| External-sharing policy           | Shared Drive must allow external members so per-principal view-only shares work |

**Code changes deferred to Phase 2B:**

- `FolderManager.provision`, `UploadSessionMint.initiate`, and any
  Drive call in the reference server: thread the `supportsAllDrives`
  kwarg through.
- A typed config loader that reads `DRIVE_WORKSPACE_SHARED_DRIVE_ID`
  and rejects empty / missing at startup (same fail-fast pattern as
  `FileAuthenticator`'s existence check).

**No code changes in this session.** The full Shared Drives flag
checklist lives in ADR-0011's Implementation notes; the integration
tests in Phase 3 are the executable proof point. Path A migration
(this document, above) is the operational gate.

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

### Remote + tags pushed

`origin` is `https://github.com/vinay1277/drive-workspace.git` (private).
`main` and the four landmark tags below are pushed:

| Tag                     | Commit    | Meaning                                          |
|-------------------------|-----------|--------------------------------------------------|
| `phase-1-complete`      | `f2d5284` | Phase 1 skeleton + ADR-0008/9 + bug-fix merge    |
| `phase-2a-complete`     | `9931cbc` | Phase 2A merge (protocols, FileAuth, stores, LogSchema) |
| `adr-0010-applied`      | `c65b49c` | ADR-0010 implementation merge                    |
| `path-b-bootstrapped`   | `0d67ec1` | This document — Path B deployment record         |
