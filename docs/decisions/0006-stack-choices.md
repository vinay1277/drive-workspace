# ADR-0006: Stack choices (Python 3.11, Flask-RESTX sync, Postgres, mypy strict)

- **Status**: accepted
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

A new repo is a chance to set technology defaults thoughtfully. Two competing
pressures:

1. **Familiarity**: SmartMeter is on Flask + Flask-RESTX + MySQL, sync,
   loose typing, no mypy. Matching this lowers the cost of moving people
   between projects.
2. **Cleanliness**: A fresh repo is a chance to fix things SmartMeter didn't
   pin down (typing, modern Python, clean test setup).

We want familiarity where it doesn't actively cost us, and cleanliness where
it costs little to adopt early.

## Decision

| Choice                | Value                                       | Rationale |
|-----------------------|---------------------------------------------|-----------|
| Python version        | 3.11+                                       | Modern typing (`Self`, `match`, runtime `Protocol`); SmartMeter can pin to whatever it's on. |
| Web framework (ref)   | Flask + Flask-RESTX, **sync**               | Matches SmartMeter idioms; sync is fine for the QPS we expect (initiate is a small handshake). Re-evaluate if QPS demands. |
| Persistence (default) | SQLAlchemy 2.x                              | Industry default; works against MySQL, Postgres, SQLite without code changes. |
| Reference DB          | Postgres 16                                 | Fresh project, fresh defaults — better SQL than MySQL, fewer SmartMeter habits leaking in. The package is DB-agnostic; this is just what `docker-compose` runs. |
| Type checking         | `mypy --strict`                             | Cheap to start, expensive to retrofit. |
| Lint                  | `ruff`                                      | Fast, no config debate. |
| Test                  | `pytest` + `responses` (HTTP mocking)       | Standard. |
| Secrets in dev        | `backend/.secrets/dev-sa.json` (gitignored) | Documented; never committed. |
| Secrets in CI         | GitHub Actions secrets, separate key from dev | Compromised CI key cannot reach dev/prod data. |
| Logging               | Python `logging`, structured                | No vendor lock-in; host configures formatters. |

## Consequences

**Positive**:
- Familiarity preserved for the parts that matter (Flask-RESTX route shapes,
  request/response patterns).
- Modern Python features available where they're worth it.
- Type-checking discipline established before code volume makes it expensive.

**Negative**:
- Reference DB is Postgres but SmartMeter's prod is MySQL. Caught at
  integration time; the package itself is DB-agnostic so the test bed
  doesn't need to match prod.
- Sync Flask blocks a thread per concurrent initiate. At 50 surveyors
  hitting the endpoint simultaneously this is unconcerning; at 5,000 it
  would be. Re-evaluate at scale.

**Rejected alternatives**:
- *FastAPI + async*: a real upgrade in the abstract; in practice the
  initiate endpoint is mostly waiting on Drive, which dominates either way.
  The async flip can happen later if demanded; the package itself is
  framework-agnostic.
- *MySQL for the reference DB*: would re-anchor us to SmartMeter's choices
  and remove the "fresh project" signal.
- *Skip mypy*: would be cheaper today, much more expensive by Phase 3.

## Implementation notes

- `pyproject.toml` is the single source of truth for Python tooling
  configuration. No `setup.cfg`, no `mypy.ini`, no `pytest.ini`.
- `mypy --strict` is enforced in CI from the very first PR with code in it.
  No "we'll fix it later."
