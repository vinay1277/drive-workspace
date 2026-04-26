# ADR-0009: Versioning and distribution

- **Status**: accepted
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

`plan.md` flagged this as gating for Phase 4: how does a consumer (initially
SmartMeter, hypothetically a second app later) pin a specific version of the
Python package and Android library? Pulling the decision forward to Phase 2
entry, because Phase 2 lands the first shippable surface (the
`DriveWorkspace` facade) and the Android library's artifact coordinates need
to match whatever distribution the backend uses.

Three plausible routes per stack:

| | Backend (Python) | Android |
|-|------------------|---------|
| Cheapest | `git+ssh` tag pinning in `requirements.txt` | Gradle `includeBuild` (composite build) |
| Mid | GitHub Releases + wheel/AAR artifact | Gradle `includeBuild` |
| Heaviest | Private PyPI (Gemfury, GitHub Packages, self-hosted) | Private Maven (GitHub Packages, Sonatype, self-hosted) |

## Decision

Until a second consumer beyond SmartMeter exists:

- **Backend**: `git+ssh` tag pinning. Consumers add a line to their
  `requirements.txt` of the form
  `drive_workspace @ git+ssh://git@github.com/<org>/drive-workspace.git@v0.1.0#subdirectory=backend`.
- **Android**: Gradle composite build. Consumers add to their
  `settings.gradle.kts`:
  ```kotlin
  includeBuild("../drive-workspace/android") {
      dependencySubstitution {
          substitute(module("com.driveworkspace:library"))
              .using(project(":library"))
      }
  }
  ```
  Then declare `implementation("com.driveworkspace:library")` in the
  consumer module.

Tag `v0.1.0` at the end of Phase 3, when the maturity checklist passes.

## Consequences

**Positive**:
- Zero infrastructure to operate. No private registry to host, secure,
  back up, or monitor.
- Zero ongoing cost.
- Both pin formats are familiar to anyone who's worked with internal Python
  or Gradle projects; no DSL to learn.
- Tag-based pinning gives semver-style release discipline: a tag is the
  unit of release.

**Negative**:
- Consumers need SSH key access to this repo. For the SmartMeter case
  that's already true; for any future consumer it's a one-time setup step.
- Composite Gradle builds couple the consumer's clean to this repo's clean;
  a malformed `build.gradle.kts` here will break the consumer's build until
  fixed. Acceptable for one consumer.
- No transitive resolution of "what version do my deps depend on" — fine,
  because we have no deps that depend on us.

**Rejected alternatives**:
- *Private PyPI / Maven now*: the operational tax (hosting, auth, backups,
  rotation) is real and recurring. Worth paying when there's a second
  consumer or a release cadence that exceeds manual tagging. Not now.
- *GitHub Releases + wheel/AAR*: better than `git+ssh` for closed-source
  third-party consumers (no SSH access required), but our consumers all
  have SSH access to this repo, so the additional CI step buys nothing.

## Implementation notes

### Tagging cadence and policy

- Maintainer tags after each merged session that lands functional code
  (not docs-only sessions). CI does **not** auto-tag.
- Semver, with project-specific interpretation:
  - **Major** (`vX.0.0`): only when a deliberate breaking change to the
    public API surface lands. Rare; document the migration in the ADR that
    proposes the breaking change.
  - **Minor** (`v0.X.0`): new feature or new public surface. The default.
  - **Patch** (`v0.x.Y`): bug fix or non-functional improvement.
- Until v1.0.0, the public API is explicitly *not* stable. Consumers pin
  exact versions and update intentionally.

### Tag command

From repo root, after merging a session that lands functional code:

```bash
git tag -a v0.x.y -m "v0.x.y — short summary"
git push origin v0.x.y
```

### Migration trigger

Re-evaluate this ADR when **any** of the following becomes true:

- A second consumer beyond SmartMeter starts using the package.
- Tagging cadence exceeds one tag per week (manual tagging becomes a chore).
- A consumer needs to install without SSH access to this repo (e.g. a
  hosted CI environment that won't accept a deploy key).

The migration target is most likely:
- **Python**: GitHub Packages PyPI (free for private repos) or self-hosted
  Gemfury.
- **Android**: GitHub Packages Maven.

Both are switchable in a single PR on the consumer side: change the pin
syntax in `requirements.txt` / `settings.gradle.kts`. The package itself
needs no changes.
