# drive_workspace — backend

Python package + reference Flask server. Phase 1: skeleton, all Drive logic
stubbed.

## Run locally (without Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .[dev,flask]
flask --app reference_server.app run --host=0.0.0.0 --port=8080
```

Smoke-test:

```bash
curl http://localhost:8080/health
# {"status": "ok"}

curl -X POST http://localhost:8080/api/drive/initiate-upload \
     -H 'Content-Type: application/json' \
     -d '{"file_name":"x","mime_type":"image/jpeg","file_size_bytes":1000}'
# {"upload_url": "...", "drive_file_id": "fake-...", "expires_at": "..."}
```

## Run with Docker (postgres + reference server)

From repo root:

```bash
docker compose up
```

Postgres is exposed on `localhost:5432` (`dev`/`dev`/`dev`); reference server
on `localhost:8080`.

## Tests, lint, types

```bash
ruff check .
mypy --strict drive_workspace/
pytest
```

Phase 1 ships no tests yet; the commands above verify configuration only.

## Layout

- `drive_workspace/` — the importable package. Phase 1 modules are stubs;
  methods raise `NotImplementedError`.
  - `workspace.py` — `DriveWorkspace` facade
  - `folders.py`, `uploads.py`, `logs.py`, `reconcile.py` — sub-managers
  - `stores/protocol.py` — `PrincipalStore` Protocol
  - `stores/sqlalchemy.py` — default impl (Phase 2)
  - `adapters/flask.py` — `make_blueprint(...)` (Phase 2)
- `reference_server/` — thin Flask demo. Phase 1 fakes Drive end-to-end so
  the Android tester can run without any real credentials.
