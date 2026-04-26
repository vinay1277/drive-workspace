"""Contract tests for ``POST /api/drive/initiate-upload``.

Covers the ADR-0003 wire shape: ``?count`` query param, array response,
cap, validation. Bytes-path PUT behaviour is exercised manually via the
tester app and is out of scope here.
"""

from __future__ import annotations

import pytest

from reference_server.app import MAX_PREFETCH_COUNT, create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_initiate_default_count_returns_array_with_one(client) -> None:
    resp = client.post(
        "/api/drive/initiate-upload",
        json={"file_size_bytes": 1234},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "sessions" in body, body
    assert isinstance(body["sessions"], list)
    assert len(body["sessions"]) == 1
    s = body["sessions"][0]
    assert s["upload_url"].endswith(s["drive_file_id"].removeprefix("fake-"))
    assert s["expires_at"] == "2099-01-01T00:00:00Z"


def test_initiate_count_n_returns_n_distinct_sessions(client) -> None:
    resp = client.post(
        "/api/drive/initiate-upload?count=5",
        json={"file_size_bytes": 1234},
    )
    assert resp.status_code == 200
    sessions = resp.get_json()["sessions"]
    assert len(sessions) == 5
    upload_urls = {s["upload_url"] for s in sessions}
    drive_ids = {s["drive_file_id"] for s in sessions}
    assert len(upload_urls) == 5, "upload_urls must be unique across the batch"
    assert len(drive_ids) == 5, "drive_file_ids must be unique across the batch"


def test_initiate_count_at_cap(client) -> None:
    resp = client.post(
        f"/api/drive/initiate-upload?count={MAX_PREFETCH_COUNT}",
        json={"file_size_bytes": 1},
    )
    assert resp.status_code == 200
    assert len(resp.get_json()["sessions"]) == MAX_PREFETCH_COUNT


def test_initiate_count_above_cap_is_rejected(client) -> None:
    resp = client.post(
        f"/api/drive/initiate-upload?count={MAX_PREFETCH_COUNT + 1}",
        json={"file_size_bytes": 1},
    )
    assert resp.status_code == 400
    assert "must be <=" in resp.get_json()["error"]


def test_initiate_count_zero_is_rejected(client) -> None:
    resp = client.post(
        "/api/drive/initiate-upload?count=0",
        json={"file_size_bytes": 1},
    )
    assert resp.status_code == 400


def test_initiate_count_non_integer_is_rejected(client) -> None:
    resp = client.post(
        "/api/drive/initiate-upload?count=abc",
        json={"file_size_bytes": 1},
    )
    assert resp.status_code == 400
