# ADR-0004: Modular backend package with host-supplied plug points

- **Status**: accepted
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

The first consumer of this work is SmartMeter, but the explicit goal is that
the *second* consumer is easy. We need to decide how much abstraction to
build and where the seams go.

Two failure modes to avoid:

1. **Under-abstraction**: package is shaped around SmartMeter concepts
   (surveys, IVRS, surveyors). Second consumer copy-pastes and forks.
2. **Over-abstraction**: package tries to anticipate every possible host;
   ships a configuration-as-code system; second consumer takes a week to
   wire it up.

## Decision

Build the package with three explicit plug points, no more:

| Plug point         | Host responsibility                                                        | Default impl ships? |
|--------------------|----------------------------------------------------------------------------|---------------------|
| `PrincipalStore`   | Persist `(principal_id → folder_id, spreadsheet_id, audit rows)`.          | Yes — SQLAlchemy.   |
| `Authenticator`    | Return a `google.oauth2.service_account.Credentials`.                      | Yes — file path.    |
| `LogSchema`        | Declare spreadsheet columns and render a row from a host-supplied dict.    | No — host writes.   |

All three are Python `Protocol`s (structural typing). Hosts implement the
methods they need; no inheritance required.

Everything else is fixed in the package: the upload flow, the folder
template logic, the chunked PUT semantics on the device, the reconciliation
algorithm. A second consumer cannot configure these; they get what we built.

The package additionally ships **optional adapters** that hosts may use or
ignore:
- `drive_workspace.adapters.flask.make_blueprint(dw, auth_decorator)` —
  mounts the standard endpoints in one line.
- (Future) `drive_workspace.adapters.fastapi`, etc.

## Consequences

**Positive**:
- Total host glue: ~80 lines (PrincipalStore wrapper, LogSchema,
  Authenticator one-liner, route wiring).
- The plug points are minimal, narrow, and don't leak the host's domain
  back into the package.
- Default `SqlAlchemyPrincipalStore` means a host with no strong opinions
  gets it free.

**Negative**:
- Hosts using a non-SQL persistence (Datastore, DynamoDB, Mongo) write
  their own `PrincipalStore`. That's the deal.
- Hosts using non-Flask frameworks today write their own routes. Adapters
  for FastAPI / Django are deferred until a second consumer asks.

**Rejected alternatives**:
- *Subclass-based extension*: more flexible but invites surprise overrides.
  Protocols are narrower and clearer.
- *Configuration files (YAML/TOML) for behavior*: pushes errors to runtime,
  invents a DSL. Pure Python construction is simpler and type-checked.
- *Auto-detect the host's ORM*: clever, fragile. Be explicit.

## Implementation notes

- `Protocol`s live in `drive_workspace/stores/protocol.py` and similar
  module-local files; they are part of the public API.
- Default impls live alongside the protocols
  (`drive_workspace/stores/sqlalchemy.py`).
- The package never imports from a host project. Test: a fresh venv with
  only `drive_workspace` installed must import and instantiate
  successfully.
