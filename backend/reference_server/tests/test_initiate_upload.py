"""Contract tests for ``POST /api/drive/initiate-upload``.

Covers the ADR-0003 wire shape: ``?count`` query param, array
response, cap, validation. Adds the basic-shape and host-resolution
bullets called out in
``docs/sessions/2026-05-02-reference-server-tests.md``.

Bytes-path PUT behaviour is exercised in :mod:`test_stub_upload`.
"""

from __future__ import annotations

from urllib.parse import urlparse

from flask.testing import FlaskClient

from reference_server.app import MAX_PREFETCH_COUNT

# ---- shape and basic semantics ---------------------------------------


def test_initiate_default_count_returns_array_with_one(
    client: FlaskClient,
) -> None:
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
    assert set(s.keys()) >= {"upload_url", "drive_file_id", "expires_at"}
    assert s["expires_at"] == "2099-01-01T00:00:00Z"


def test_drive_file_id_uses_fake_prefix(client: FlaskClient) -> None:
    """Phase 1 stub minted ids must be obviously fake."""
    resp = client.post(
        "/api/drive/initiate-upload",
        json={"file_size_bytes": 1},
    )
    s = resp.get_json()["sessions"][0]
    assert s["drive_file_id"].startswith("fake-"), s["drive_file_id"]


def test_upload_url_resolves_to_request_host(client: FlaskClient) -> None:
    """``upload_url`` lives on the same host as the initiate request.

    The Phase 1 stub server is also the chunk-PUT target, so the host
    must round-trip; if it ever drifts (for example by hard-coding a
    different base) the chunked PUT would fail in the field.
    """
    resp = client.post(
        "/api/drive/initiate-upload",
        json={"file_size_bytes": 1},
        # Flask test_client defaults host to "localhost"; pin it
        # explicitly so the assertion is meaningful regardless of any
        # default change.
        headers={"Host": "test-host.example"},
    )
    s = resp.get_json()["sessions"][0]
    parsed = urlparse(s["upload_url"])
    assert parsed.netloc == "test-host.example", s["upload_url"]
    assert parsed.path.startswith("/_stub/upload/"), s["upload_url"]


def test_two_consecutive_initiates_produce_distinct_ids(
    client: FlaskClient,
) -> None:
    first = client.post(
        "/api/drive/initiate-upload",
        json={"file_size_bytes": 1},
    ).get_json()["sessions"][0]
    second = client.post(
        "/api/drive/initiate-upload",
        json={"file_size_bytes": 1},
    ).get_json()["sessions"][0]
    assert first["drive_file_id"] != second["drive_file_id"]
    assert first["upload_url"] != second["upload_url"]


def test_initiate_with_no_body_still_succeeds(client: FlaskClient) -> None:
    """A missing JSON body means file_size_bytes = 0; valid for the
    stub. This path matters because the prefetch flow legitimately
    sends a 1-byte placeholder (or nothing) when minting a batch
    template ahead of knowing real file sizes."""
    resp = client.post("/api/drive/initiate-upload")
    assert resp.status_code == 200
    assert len(resp.get_json()["sessions"]) == 1


# ---- ?count parameter (ADR-0003 prefetch) ---------------------------


def test_initiate_count_n_returns_n_distinct_sessions(
    client: FlaskClient,
) -> None:
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


def test_initiate_count_at_cap(client: FlaskClient) -> None:
    resp = client.post(
        f"/api/drive/initiate-upload?count={MAX_PREFETCH_COUNT}",
        json={"file_size_bytes": 1},
    )
    assert resp.status_code == 200
    assert len(resp.get_json()["sessions"]) == MAX_PREFETCH_COUNT


def test_initiate_count_above_cap_is_rejected(client: FlaskClient) -> None:
    resp = client.post(
        f"/api/drive/initiate-upload?count={MAX_PREFETCH_COUNT + 1}",
        json={"file_size_bytes": 1},
    )
    assert resp.status_code == 400
    assert "must be <=" in resp.get_json()["error"]


def test_initiate_count_zero_is_rejected(client: FlaskClient) -> None:
    resp = client.post(
        "/api/drive/initiate-upload?count=0",
        json={"file_size_bytes": 1},
    )
    assert resp.status_code == 400


def test_initiate_count_negative_is_rejected(client: FlaskClient) -> None:
    resp = client.post(
        "/api/drive/initiate-upload?count=-1",
        json={"file_size_bytes": 1},
    )
    assert resp.status_code == 400


def test_initiate_count_non_integer_is_rejected(client: FlaskClient) -> None:
    resp = client.post(
        "/api/drive/initiate-upload?count=abc",
        json={"file_size_bytes": 1},
    )
    assert resp.status_code == 400
