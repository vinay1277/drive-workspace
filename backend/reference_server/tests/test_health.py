"""Tests for ``GET /health`` — the liveness probe."""

from __future__ import annotations

from flask.testing import FlaskClient


def test_health_returns_ok(client: FlaskClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_health_is_idempotent(client: FlaskClient) -> None:
    """Two consecutive calls return the same body — no per-call state."""
    first = client.get("/health").get_json()
    second = client.get("/health").get_json()
    assert first == second
