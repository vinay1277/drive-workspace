# ADR-0008: Test Workspace ownership

- **Status**: accepted
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

Phase 2 needs a real Google Workspace context to point the test
service-account at: an org-owned root folder, a `Templates/` subtree, a
spreadsheet template, and the ability to share per-principal folders
view-only with arbitrary email addresses.

This decision shapes Phase 2.1 (Provision the test Workspace + service
account + test root folder), Phase 2.2 (`Authenticator` impl), Phase 3.2
(integration tests in CI against real Drive), and the Phase 4 SmartMeter
integration story.

## Decision

Use a **dedicated subfolder of the existing org Workspace** rather than
standing up a separate Workspace tenant. Scoping is enforced by:

1. The service account's `drive.file` OAuth scope, which restricts visibility
   to files the SA has explicitly created or been granted access to.
2. Folder-level ACLs on the test root folder.
3. A clear naming convention (`/drive-workspace-test/`) so the test root is
   never confused with operational SmartMeter folders.

## Consequences

**Positive**:
- No additional Workspace seat cost (~$6/mo saved per admin user).
- Test bed structurally matches the Phase 4 SmartMeter production target —
  same tenant, same admin console, same SA management workflow. The Phase 4
  configuration delta is small (new root folder ID, new SA, possibly a
  different `parents:` list).
- One Google Cloud project to operate, not two.

**Negative**:
- Tighter scoping discipline required: SA's grants must stay folder-scoped
  and the `drive.file` scope must not be widened to `drive` without revisiting
  this ADR. The operational guardrail: every SA created under this scheme
  should be reviewed annually for scope creep.
- A misconfigured SA could in theory be granted access to operational data
  by an admin who clicks through too fast. Mitigation: no ad-hoc shares to
  the test SA from outside the test root folder; treat sharing-into-test
  the same as a code change.

**Rejected alternative**:
- *Separate Workspace tenant*: cleanest blast-radius isolation but adds a
  paid seat, separate admin console, separate DNS for the test domain, and
  a configuration delta that crosses the Phase 4 boundary. The cost-vs.-risk
  trade did not pencil out for an in-house proprietary project with one
  consumer in planning.

## Implementation notes

When the test bed is provisioned (Phase 2.1), record the actual values in
`docs/deployment.md`. Convention to follow:

| Item                           | Convention                                                    |
|--------------------------------|---------------------------------------------------------------|
| Test root folder name          | `drive-workspace-test` at Drive root in the org Workspace     |
| Test root folder ID            | Captured in `docs/deployment.md`; referenced via env in code  |
| Service account email          | `drive-workspace-test-sa@<gcp-project>.iam.gserviceaccount.com` |
| OAuth scopes                   | `https://www.googleapis.com/auth/drive.file` + `https://www.googleapis.com/auth/spreadsheets` |
| Local SA key path              | `backend/.secrets/dev-sa.json` (gitignored — already in `.gitignore`) |
| CI secret name (GitHub Actions)| `DRIVE_WORKSPACE_TEST_SA_KEY`                                 |
| Env var the reference server reads | `DRIVE_WORKSPACE_SA_KEY_PATH` (path to JSON file at runtime) |
| Env var for test root folder   | `DRIVE_WORKSPACE_ROOT_FOLDER_ID`                              |

The CI key MUST be a different physical SA key from the local-dev key. Both
SAs may share the same email or be separate; rotate either independently.

Annual review (calendar reminder): confirm the SA still has only
`drive.file` + `spreadsheets` scope and no shares outside the test root
folder.
