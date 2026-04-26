# ADR-0008: Test Workspace ownership

- **Status**: proposed (decision pending — see "Decision required" below)
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

Phase 2 needs a real Google Workspace context to point the test
service-account at: an org-owned root folder, a `Templates/` subtree, a
spreadsheet template, and the ability to share per-principal folders
view-only with arbitrary email addresses.

Two routes:

1. **Stand up a separate Workspace domain** (e.g. a fresh
   `drive-workspace-test.example.com` tenant) used only by this project.
   Test data, test users, and test SAs live entirely there; nothing the
   project does can touch the operational SmartMeter Workspace.
2. **Use a subfolder of the existing org Workspace** (presumably the same
   tenant SmartMeter is already on), with a dedicated root folder and SA
   scoped to that subtree.

This decision shapes Phase 2.1 (Provision the test Workspace + service
account + test root folder), Phase 2.2 (`Authenticator` impl), Phase 3.2
(integration tests in CI against real Drive), and the Phase 4 SmartMeter
integration story.

## Decision required

The session writer cannot resolve this — it is an
operational/cost/governance call by the maintainer:

- **Cost**: a separate Workspace tenant is a paid Google Workspace seat
  for at least one admin user per month. Subfolder-of-existing-tenant is
  free.
- **Blast radius**: separate tenant = misconfigured SA cannot read
  production SmartMeter data. Same tenant = tighter scoping discipline
  required (SA's `domain-wide delegation` and folder ACLs are the only
  guards).
- **CI integration**: the chosen tenant's SA credential is the secret CI
  loads (ADR-0006 already pins this to `secrets/dev-sa.json` locally and
  GitHub Actions secret in CI). Either route works; the secret name and
  layout are unchanged.
- **End-to-end realism**: Phase 4 (SmartMeter integration) eventually
  needs to upload into SmartMeter's *production* Workspace. Choosing the
  same-tenant route means the Phase 2/3 test bed structurally matches the
  Phase 4 production target. Choosing a separate tenant means a small
  configuration delta (new root folder ID, new SA) crosses the Phase 4
  boundary.

## Decision (fill in when made)

> *To be decided.* When chosen, edit this section, set Status to
> `accepted`, and add an Implementation notes section listing: the chosen
> root folder ID, the SA email, the secret name, and which env var the
> reference server reads them from.

## Consequences

To be filled in when decided.

## Implementation notes

To be filled in when decided.
