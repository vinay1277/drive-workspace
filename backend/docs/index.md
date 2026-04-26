# drive_workspace

> Backend-mediated Google Drive uploads, per-principal folders, and
> spreadsheet logs.
>
> This site is the API reference auto-generated from the package's
> docstrings. For the architecture overview, the rationale ADRs, and
> the operating guide, see the project root: [`README.md`](https://github.com/vinay1277/drive-workspace#readme),
> [`docs/architecture.md`](https://github.com/vinay1277/drive-workspace/blob/main/docs/architecture.md),
> [`docs/decisions/`](https://github.com/vinay1277/drive-workspace/tree/main/docs/decisions).

## Build status

This first cut allows Sphinx warnings. Phase 3 hardens to
`sphinx-build -W` (warnings as errors) and adds a CI step — see
`docs/plan.md`.

## Quick orientation

The package has three **plug points** the host application implements
(per [ADR-0004](https://github.com/vinay1277/drive-workspace/blob/main/docs/decisions/0004-modular-package-with-host-plugins.md)):

| Plug point         | Host responsibility                                                          | Default impl ships? |
|--------------------|------------------------------------------------------------------------------|---------------------|
| `PrincipalStore`   | Persist `(principal_id → folder_id, spreadsheet_id, audit rows)`             | Yes — SQLAlchemy 2.x |
| `Authenticator`    | Return a `google.oauth2.service_account.Credentials`                          | Yes — file-path     |
| `LogSchema`        | Declare spreadsheet columns and render a row from a host-supplied dict       | No — host writes    |

Everything else is fixed in the package: the upload flow, folder
template logic, chunked PUT semantics, reconciliation. The optional
Flask adapter (`make_blueprint`) wraps the standard endpoints in one
line for hosts on Flask.

## API reference

The auto-generated reference for every public symbol exported by
`drive_workspace.__init__.__all__` (and the `stores`, `adapters`
sub-packages) is available below.

```{toctree}
:maxdepth: 2
:caption: Contents

apidocs/index
```

## Building these docs

```bash
pip install -e .[docs]
cd backend/docs
sphinx-build -b html . _build
# open _build/html/index.html
```
