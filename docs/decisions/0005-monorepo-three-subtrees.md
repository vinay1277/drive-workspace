# ADR-0005: Monorepo with three sub-trees

- **Status**: accepted
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

The project has three deliverables that must stay aligned: a Python backend
package, an Android client library, and end-to-end tests that exercise both.
Two layout options:

1. **Polyrepo**: separate repos for backend, Android, and shared docs.
2. **Monorepo**: one repo, three sub-trees, shared docs and CI.

The asset that has to stay in sync is the **wire contract** between backend
and Android client. Anything that risks contract drift is a problem.

## Decision

Single monorepo. Three top-level sub-trees:

```
drive-workspace/
├── backend/           # Python package + reference Flask server
├── android/           # Gradle library + tester app
├── integration-tests/ # E2E against real Drive
└── docs/              # architecture, ADRs, plan, sessions
```

CI runs three pipelines (backend, Android, e2e) but they live in
`.github/workflows/` of the single repo.

## Consequences

**Positive**:
- A contract change is one PR that touches `backend/`, `android/`, and
  `docs/architecture.md` atomically. Reviewer sees the full surface in one
  diff.
- The integration-tests sub-tree has a natural home; in a polyrepo it would
  be either a third repo (more infra) or wedged into one of the two.
- Shared docs are obvious: `docs/` belongs to everyone.
- Onboarding: `git clone` once, see the whole project.

**Negative**:
- The Android consumer (eventually SmartMeter's app/) doesn't need the
  backend code; cloning gets them more than they need. Acceptable —
  `git sparse-checkout` exists for the rare case.
- Future Android-only release builds need to know to ignore `backend/`.
  Trivially handled in CI workflow filters.

**Rejected alternatives**:
- *Polyrepo*: would require either (a) a shared "contract" repo that both
  others depend on (overengineered) or (b) accepting drift (unacceptable).
- *Submodule of SmartMeter*: would re-couple us to SmartMeter — the
  whole point of this repo is to break that coupling.

## Implementation notes

- Branch protection on `main`: required CI passes (backend tests, Android
  build, e2e on a schedule).
- Conventional commits encouraged but not enforced; the value here is small
  for a small team.
- When v1.0 is reached and a second consumer adopts the package, we
  re-evaluate splitting. Until then, monorepo wins.
