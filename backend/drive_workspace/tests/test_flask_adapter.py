"""Unit tests for drive_workspace.adapters.flask.make_blueprint.

Uses flask.Flask().test_client() and a fake DriveWorkspace whose
``uploads.initiate`` and ``logs.append`` return canned values. No real
Drive contact, no real DriveWorkspace construction (the adapter only
touches ``dw.uploads`` and ``dw.logs``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast
from unittest.mock import MagicMock

import pytest
from flask import Flask, Response, g

from drive_workspace import MAX_PREFETCH_COUNT
from drive_workspace.adapters.flask import make_blueprint
from drive_workspace.uploads import UploadSession

F = TypeVar("F", bound=Callable[..., Any])


def _fake_dw(*, principal_id_seen: list[str] | None = None) -> Any:
    """Build a MagicMock standing in for DriveWorkspace.

    ``uploads.initiate`` returns one canned UploadSession per requested
    file; ``logs.append`` records the principal_id it saw so the test
    can assert it.
    """
    dw = MagicMock()

    def _initiate(principal_id: str, files: list[Any]) -> list[UploadSession]:
        if principal_id_seen is not None:
            principal_id_seen.append(principal_id)
        return [
            UploadSession(
                upload_url=f"https://example.invalid/upload/{i}",
                drive_file_id=f"fake-{i}",
                expires_at="2099-01-01T00:00:00Z",
            )
            for i in range(len(files))
        ]

    def _append(principal_id: str, row: dict[str, Any]) -> None:
        if principal_id_seen is not None:
            principal_id_seen.append(principal_id)

    dw.uploads.initiate.side_effect = _initiate
    dw.logs.append.side_effect = _append
    return dw


def _app(
    dw: Any,
    *,
    auth_decorator: Callable[[F], F] | None = None,
    set_principal_id: str | None = "alice",
    url_prefix: str = "/api/drive",
) -> Flask:
    app = Flask(__name__)
    app.testing = True
    if set_principal_id is not None:

        @app.before_request
        def _stash_pid() -> None:
            g.principal_id = set_principal_id

    app.register_blueprint(
        make_blueprint(dw, auth_decorator=auth_decorator, url_prefix=url_prefix)
    )
    return app


# -----------------------------------------------------------------------------
# initiate-upload
# -----------------------------------------------------------------------------


def test_initiate_upload_count_default_returns_one_session() -> None:
    seen: list[str] = []
    dw = _fake_dw(principal_id_seen=seen)
    client = _app(dw).test_client()

    resp = client.post(
        "/api/drive/initiate-upload",
        json={"file_name": "img.jpg", "mime_type": "image/jpeg",
              "file_size_bytes": 1024, "kind_hint": "photo"},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body["sessions"], list) and len(body["sessions"]) == 1
    s = body["sessions"][0]
    assert set(s.keys()) == {"upload_url", "drive_file_id", "expires_at"}
    assert seen == ["alice"]


def test_initiate_upload_count_n_returns_n_sessions() -> None:
    dw = _fake_dw()
    client = _app(dw).test_client()

    resp = client.post(
        "/api/drive/initiate-upload?count=5",
        json={"file_name": "img.jpg", "mime_type": "image/jpeg"},
    )

    assert resp.status_code == 200
    assert len(resp.get_json()["sessions"]) == 5


def test_initiate_upload_count_at_cap_succeeds() -> None:
    dw = _fake_dw()
    client = _app(dw).test_client()

    resp = client.post(
        f"/api/drive/initiate-upload?count={MAX_PREFETCH_COUNT}",
        json={"file_name": "img.jpg"},
    )

    assert resp.status_code == 200
    assert len(resp.get_json()["sessions"]) == MAX_PREFETCH_COUNT


def test_initiate_upload_count_over_cap_returns_400() -> None:
    dw = _fake_dw()
    client = _app(dw).test_client()

    resp = client.post(
        f"/api/drive/initiate-upload?count={MAX_PREFETCH_COUNT + 1}",
        json={},
    )

    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_initiate_upload_count_zero_returns_400() -> None:
    dw = _fake_dw()
    client = _app(dw).test_client()

    resp = client.post("/api/drive/initiate-upload?count=0", json={})

    assert resp.status_code == 400


def test_initiate_upload_count_non_integer_returns_400() -> None:
    dw = _fake_dw()
    client = _app(dw).test_client()

    resp = client.post("/api/drive/initiate-upload?count=abc", json={})

    assert resp.status_code == 400


# -----------------------------------------------------------------------------
# submission
# -----------------------------------------------------------------------------


def test_submission_calls_logs_append_and_returns_ok() -> None:
    seen: list[str] = []
    dw = _fake_dw(principal_id_seen=seen)
    client = _app(dw).test_client()

    resp = client.post(
        "/api/drive/submission",
        json={"timestamp": "2026-05-05T00:00:00Z", "status": "submitted"},
    )

    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}
    assert seen == ["alice"]
    dw.logs.append.assert_called_once()
    _, kwargs = dw.logs.append.call_args
    assert kwargs["principal_id"] == "alice"
    assert kwargs["row"]["status"] == "submitted"


# -----------------------------------------------------------------------------
# Missing principal_id — host contract violation, surfaces as 500
# -----------------------------------------------------------------------------


def test_missing_principal_id_surfaces_as_500() -> None:
    """The blueprint never returns 401. If g.principal_id is unset the
    host violated the contract; Flask's default error handler raises 500."""
    dw = _fake_dw()
    app = _app(dw, set_principal_id=None)
    app.testing = False  # let the error propagate to a 500 response
    client = app.test_client()

    resp = client.post("/api/drive/initiate-upload", json={})

    assert resp.status_code == 500


# -----------------------------------------------------------------------------
# auth_decorator wraps both routes
# -----------------------------------------------------------------------------


def test_auth_decorator_wraps_both_routes() -> None:
    calls: list[str] = []

    def deco(view: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            calls.append(view.__name__)
            return view(*args, **kwargs)

        wrapper.__name__ = view.__name__
        return cast(F, wrapper)

    dw = _fake_dw()
    client = _app(dw, auth_decorator=deco).test_client()

    r1 = client.post("/api/drive/initiate-upload", json={})
    r2 = client.post("/api/drive/submission", json={})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert calls == ["initiate_upload", "record_submission"]


def test_auth_decorator_can_short_circuit_with_401() -> None:
    """Confirms the host's decorator (not the blueprint) owns 401."""

    def deny(view: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return Response('{"error": "unauthenticated"}', status=401,
                            mimetype="application/json")

        wrapper.__name__ = view.__name__
        return cast(F, wrapper)

    dw = _fake_dw()
    client = _app(dw, auth_decorator=deny).test_client()

    resp = client.post("/api/drive/initiate-upload", json={})

    assert resp.status_code == 401


# -----------------------------------------------------------------------------
# url_prefix override
# -----------------------------------------------------------------------------


def test_custom_url_prefix() -> None:
    dw = _fake_dw()
    client = _app(dw, url_prefix="/v2/drive").test_client()

    resp = client.post("/v2/drive/initiate-upload", json={})

    assert resp.status_code == 200


def test_default_prefix_404_under_alternate_path() -> None:
    dw = _fake_dw()
    client = _app(dw, url_prefix="/v2/drive").test_client()

    resp = client.post("/api/drive/initiate-upload", json={})

    assert resp.status_code == 404


# Suppress unused-import noise from cast/pytest in some configurations.
_ = pytest
