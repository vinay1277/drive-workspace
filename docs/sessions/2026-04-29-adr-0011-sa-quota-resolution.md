# Session: 2026-04-29 — ADR-0011: SA-quota resolution (Shared Drives vs DWD)

> **Decision-shaped session.** No code changes. Output is a single new ADR
> that picks how Phase 2B will work around the service-account
> file-creation quota issue surfaced in `docs/deployment.md` "Path B —
> known limitations". Without this decision, Phase 2B (`FolderManager.provision`,
> `UploadSessionMint.initiate`, `SpreadsheetLogger.append`) cannot create
> any files in user-owned Drive folders.

## Goal

Land [`docs/decisions/0011-sa-storage-quota.md`](../decisions/0011-sa-storage-quota.md)
as `accepted` with concrete implementation notes — picking Shared Drives,
Domain-Wide Delegation, or a hybrid. The package code may need a small
change (`FileAuthenticator` likely gains a `subject` parameter for
impersonation if DWD wins); if so, do that change in this same session.

## Required reading (before writing the ADR)

- `docs/deployment.md` — full document, especially "Path B — known
  limitations" §1 (the failure mode this ADR resolves)
- `docs/decisions/0001-backend-mediated-uploads.md` (trust boundary; the SA
  is the only Drive credential and lives server-side)
- `docs/decisions/0002-per-principal-folders-org-owned.md` (per-principal
  folder creation is the operation that hits the quota)
- `docs/decisions/0008-test-workspace-ownership.md` (current test bed)
- The Sheet-creation 403 captured in
  `backend/.secrets/bootstrap_test_workspace.py` output (logged in
  `docs/deployment.md`)
- Google's docs:
  - <https://developers.google.com/drive/api/guides/about-shareddrives>
  - <https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority>

Do not read prior session transcripts.

## In scope

### The ADR

- New file `docs/decisions/0011-sa-storage-quota.md` using
  `docs/decisions/_template.md`.
- Status: `accepted` (not `proposed`) — this session decides.
- Three options to compare in the body:
  1. **Shared Drives**: SA added as member, files in Shared Drive count
     against org pooled quota. Requires Workspace Business Standard+ tier
     (NOT available on personal Gmail).
  2. **Domain-Wide Delegation (DWD)**: SA impersonates a real Workspace
     user (`subject=user@org.com`); created files belong to that user.
     Requires Workspace admin grant, available on any Workspace plan.
  3. **Hybrid**: Shared Drive for Master/Templates (org-owned, never
     touched by surveyor); DWD for Principals (per-principal folders
     impersonating each principal's account).
- Rejected alternatives must include: "leave SA unchanged" (the failure
  mode we observed) and "use OAuth user-flow as in legacy SmartMeter"
  (contradicts ADR-0001).

### Decision criteria (work through explicitly)

- Cost: Workspace plan tier required; per-seat impact
- Operational complexity: who runs the admin console, who rotates,
  how onboarding works
- Blast-radius: what happens when impersonation goes wrong vs. what
  happens when a Shared Drive ACL goes wrong
- Code surface: how much of `drive_workspace` changes
- Compatibility with `meternnj-org` specifically (the maintainer's
  current Workspace context — confirm Shared Drives availability)

### Code changes (only if the chosen option needs them)

If DWD wins: add `subject: str | None = None` parameter to
`FileAuthenticator.__init__`, threaded through to
`Credentials.from_service_account_file(...).with_subject(subject)`.
Keep the existing tests green; add a unit test that asserts the
returned credential carries the `_subject` attribute when set.

If Shared Drives wins: no library code change in this session. Note in
the ADR that `drive_workspace.uploads` and `drive_workspace.folders`
must pass `supportsAllDrives=True` and `includeItemsFromAllDrives=True`
on every Drive API call when Phase 2B implements them.

If hybrid: a mix of the above.

## Out of scope

- Migrating the actual test bed to the new approach. That happens after
  Google's account verification clears (see Path A migration plan in
  `docs/deployment.md`).
- Implementing `FolderManager.provision`, `UploadSessionMint.initiate`,
  or `SpreadsheetLogger.append`. Those are Phase 2B.
- Re-running `bootstrap_test_workspace.py` against Shared Drive / DWD.
  Phase 2B will exercise this for real; no need to prove it ahead of time.

## Definition of done

- [ ] `docs/decisions/0011-sa-storage-quota.md` exists, status `accepted`,
      includes Decision, Consequences (positive/negative/rejected), and
      concrete Implementation notes naming the env vars / config flags /
      code paths Phase 2B will touch.
- [ ] If DWD or Hybrid: `FileAuthenticator` updated, existing
      `test_auth.py` still green, one new test for the `subject`
      parameter.
- [ ] If Shared Drives only: a one-paragraph "Shared Drives flag
      checklist" embedded in the ADR Implementation notes section.
- [ ] `docs/deployment.md` updated with a new section "Phase 2B prep:
      ADR-0011 chosen approach" replacing the speculative "fix" bullets
      under "Path B — known limitations" §1.
- [ ] One commit. Message references this brief filename.

## Notes / open questions

1. **Confirm `meternnj-org` Workspace tier** — does the maintainer's
   current Workspace plan include Shared Drives? If not, that takes
   option 1 and the hybrid off the table mechanically. The maintainer
   should check admin.google.com → Storage → Shared Drives before the
   session starts; if uncertain, default to DWD.
2. **DWD impersonation target** — for the test bed, who does the SA
   impersonate? Recommend: a dedicated test user (e.g.
   `drive-workspace-bot@meternnj-org`). For production, recommend: a
   per-host principal (the host app decides per call). The ADR locks
   this convention.
3. **Per-principal folder ownership under DWD** — when impersonating
   user X to create user Y's folder, the folder is owned by user X
   (not Y). Document this: org owns everything; the impersonation
   target is just the "create as" actor.

## Outcome

> Filled in at end of session.

(blank — to be completed)
