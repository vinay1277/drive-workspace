# ADR-0009: Versioning and distribution

- **Status**: proposed (decision pending — see "Decision required" below)
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

`plan.md` flags this as gating for Phase 4: "Decide versioning +
distribution (`git+ssh` tag vs. private PyPI) before Phase 4." Pulling
the decision forward to Phase 2 entry, because Phase 2 lands the first
shippable surface (the `DriveWorkspace` facade) and the Android library's
artifact coordinates need to match whatever distribution the backend uses.

Three plausible routes for the Python package:

1. **`git+ssh` tag pinning**: SmartMeter's `requirements.txt` pins
   `drive_workspace @ git+ssh://...@v0.1.0`. No package registry. Cheapest
   to set up; relies on SSH key access to this repo from the consumer's
   build env.
2. **Private PyPI** (e.g. self-hosted Gitea/Gemfury, or a private GitHub
   Packages PyPI). Standard `pip install` from a private index. More
   infra to run; nicer consumer ergonomics; supports semver resolution.
3. **GitHub Releases + wheel artifact**: build a wheel in CI, attach to a
   GitHub Release, install via `pip install
   https://github.com/.../releases/download/v0.1.0/drive_workspace-0.1.0-py3-none-any.whl`.
   No private index needed; auth via GitHub token.

For the Android library, the analogous choices are: include-as-source
(`includeBuild`), JitPack against this repo, or a private Maven
(GitHub Packages, Sonatype, self-hosted).

## Decision required

The session writer cannot resolve this — depends on what infra the
maintainer is willing to operate. Inputs needed:

- Does the consumer (SmartMeter) have SSH key access to this repo's
  remote?
- Is there an existing private PyPI / Maven registry the maintainer
  already pays for or runs?
- Is "build a wheel in CI, attach to GitHub Release" acceptable as the
  v0.1 distribution?

Recommendation (non-binding): start with **`git+ssh` tag pinning** for
backend and **`includeBuild`** for Android (i.e. SmartMeter clones this
repo as a Gradle composite build). Both are zero-infra. Migrate to a
private registry only when a second consumer beyond SmartMeter shows up.
Tag `v0.1.0` at the end of Phase 3 either way.

## Decision (fill in when made)

> *To be decided.* When chosen, edit this section, set Status to
> `accepted`, and add Implementation notes covering: how a consumer pins,
> how CI publishes (if it does), and the version-bump cadence.

## Consequences

To be filled in when decided.

## Implementation notes

To be filled in when decided.
