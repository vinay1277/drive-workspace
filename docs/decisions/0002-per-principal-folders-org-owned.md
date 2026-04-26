# ADR-0002: Per-principal folders, org-owned, view-only share

- **Status**: accepted
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

Drive folder structure for field uploads can be organized in several ways:

1. **Single shared bucket** — every surveyor uploads into one folder. Simple,
   but no per-principal organization, hard to audit, hard to revoke access
   without revoking everyone's.
2. **Per-principal folder, principal-owned** — surveyor signs in with their
   Google account, owns their folder. Org has limited control; offboarding
   means transferring ownership; surveyor can delete files.
3. **Per-principal folder, org-owned, shared with principal** — org's SA
   creates and owns a folder; grants the principal access via Drive sharing.
   Org retains full control; principal sees their folder via drive.google.com.

Within option 3, the share can be **edit** (principal can upload via Drive
UI, delete files) or **view-only** (principal can browse, cannot mutate).

## Decision

Adopt option 3 with **view-only** share.

- The org's SA creates `/Principals/<name>/` (subfolders for `photos`, `audio`,
  `videos`, plus a per-principal log spreadsheet copied from a template).
- The folder is shared `viewer` with the principal's Google email.
- The principal can browse the folder + spreadsheet from drive.google.com on
  any device, but cannot delete, rename, move, or upload directly.
- Uploads happen via the SA-mediated path (ADR-0001); files land in the
  folder because the backend sets `parents: [<folder_id>]` when minting the
  resumable session.

## Consequences

**Positive**:
- Org owns every byte from creation. No ownership transfer on offboarding.
- Chain of custody is intact: principal cannot tamper with their own
  uploads after submission. Important for evidentiary use cases (utility
  meter photos as billing-dispute evidence).
- Offboarding is one Drive API call: revoke the share. Files stay; access
  drops. No "who owns Alice's folder now?" question.
- Per-principal audit and quota visibility for free.
- Drive web UI is a free presentation layer — surveyors get a confidence
  signal ("did my upload land?") without us building a UI for it.

**Negative**:
- Onboarding is more work than option 1: copy template, share, persist
  mapping. ~50 lines of Python. Acceptable.
- Each principal must have a Google account that can receive the share.
  Personal Gmail works; Workspace seats are not required for view-only
  recipients.

**Rejected alternatives**:
- *Edit share*: gives the principal a chain-of-custody hole (delete /
  replace post-upload). Not worth the modest convenience of "principal can
  drag-drop into Drive UI." Re-evaluate if a workflow genuinely needs it,
  case by case.
- *Principal-owned folders*: ownership transfer on offboarding is a known
  Workspace pain point; surveyor leaving means an admin step per surveyor.

## Implementation notes

- Folder IDs persisted via `PrincipalStore` (host-supplied; default
  `SqlAlchemyPrincipalStore` ships with the package).
- Template structure lives at `/Templates/PrincipalFolderTemplate/` in the
  org's Drive; provisioning copies it via Drive `files.copy`.
- Per-principal spreadsheet is a copy of the template sheet; new rows
  appended via Sheets API by `SpreadsheetLogger`.
