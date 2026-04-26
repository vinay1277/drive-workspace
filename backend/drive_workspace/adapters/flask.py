"""Flask adapter — ``make_blueprint(dw, auth_decorator)``.

Mounts the two backend endpoints documented in
``docs/BACKEND_CONTRACT.md``:

- ``POST {url_prefix}/initiate-upload[?count=N]`` — mints N resumable
  upload sessions and returns ``{"sessions": [...]}``.
- ``POST {url_prefix}/submission`` — appends one row to the principal's
  log spreadsheet and returns ``{"ok": true}``.

The default ``url_prefix`` is ``/api/drive`` (the canonical path the
reference server and ``BACKEND_CONTRACT.md`` document); hosts that
mount under a different prefix override it.

**Host contract — principal_id is read from ``flask.g.principal_id``.**
The package can't know the host's auth shape, so the host's auth
decorator is responsible for resolving the JWT / token / session and
setting ``flask.g.principal_id: str`` before the view runs. Pass that
decorator as ``auth_decorator`` and ``make_blueprint`` wraps both
routes with it; tests that don't need an auth layer can omit it and
set ``flask.g.principal_id`` directly via a ``before_request`` hook.

**Status codes the blueprint itself returns.**

- ``200`` on success.
- ``400`` for malformed ``count`` (non-integer, ``< 1``, ``>
  MAX_PREFETCH_COUNT``).

The blueprint never returns ``401``. Authentication is the host
decorator's responsibility; if ``g.principal_id`` is missing the
host has violated the contract and Flask's default 500 surfaces the
programmer error rather than masking it as a soft 401.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from flask import Blueprint, Response, g, jsonify, request

from drive_workspace import MAX_PREFETCH_COUNT
from drive_workspace.uploads import FileSpec
from drive_workspace.workspace import DriveWorkspace

F = TypeVar("F", bound=Callable[..., Any])


def make_blueprint(
    dw: DriveWorkspace,
    auth_decorator: Callable[[F], F] | None = None,
    url_prefix: str = "/api/drive",
) -> Blueprint:
    """Build the standard drive_workspace Flask blueprint.

    See module docstring for the wire contract and host responsibilities.
    """
    bp = Blueprint("drive_workspace", __name__, url_prefix=url_prefix)

    def _decorate(view: Callable[[], Response]) -> Callable[[], Response]:
        if auth_decorator is None:
            return view
        # The TypeVar-bound auth_decorator preserves the callable's signature
        # at the host's call site; the cast here is a typing concession because
        # the local view's concrete type narrows F to a specific Callable.
        decorated: Callable[[], Response] = auth_decorator(view)  # type: ignore[arg-type]
        return decorated

    @bp.post("/initiate-upload")
    @_decorate
    def initiate_upload() -> Response:
        raw_count = request.args.get("count", "1")
        try:
            count = int(raw_count)
        except ValueError:
            return _bad_request(f"count must be an integer, got {raw_count!r}")
        if count < 1:
            return _bad_request(f"count must be >= 1, got {count}")
        if count > MAX_PREFETCH_COUNT:
            return _bad_request(
                f"count must be <= {MAX_PREFETCH_COUNT}, got {count}"
            )

        body = request.get_json(silent=True) or {}
        spec = FileSpec(
            file_name=str(body.get("file_name", "upload")),
            mime_type=str(body.get("mime_type", "application/octet-stream")),
            file_size_bytes=int(body.get("file_size_bytes", 0) or 1),
            kind=str(body.get("kind_hint") or "photo"),
        )

        sessions = dw.uploads.initiate(
            principal_id=g.principal_id,
            files=[spec] * count,
        )
        return jsonify(
            {
                "sessions": [
                    {
                        "upload_url": s.upload_url,
                        "drive_file_id": s.drive_file_id,
                        "expires_at": s.expires_at,
                    }
                    for s in sessions
                ],
            }
        )

    @bp.post("/submission")
    @_decorate
    def record_submission() -> Response:
        payload = request.get_json(silent=True) or {}
        dw.logs.append(principal_id=g.principal_id, row=payload)
        return jsonify({"ok": True})

    return bp


def _bad_request(message: str) -> Response:
    resp = jsonify({"error": message})
    resp.status_code = 400
    return resp
