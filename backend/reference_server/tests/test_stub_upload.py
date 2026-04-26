"""Lifecycle tests for ``PUT /_stub/upload/<id>``.

This is the chunk-PUT target that the Android library's
``ResumableUploadEngine`` talks to in the Phase 1 wire path. The stub
implements a small slice of the Drive resumable protocol: ``308`` with
a ``Range`` header between chunks, ``200`` with a Drive-shaped JSON
body on the final chunk, ``404`` for unknown / completed sessions.

These tests cover the state-machine paths the brief calls out
(``docs/sessions/2026-05-02-reference-server-tests.md``):

  - 404 on unknown id (never minted, or already completed)
  - single-shot full upload (one PUT == file)
  - two consecutive partial PUTs (308 → 200; intermediate ``Range``)
  - out-of-order PUT (server's high-water-mark behaviour)
  - PUT after completion (session popped from in-memory map)
  - PUT without Content-Range (single-shot path)
"""

from __future__ import annotations

from flask.testing import FlaskClient


def _initiate(client: FlaskClient, file_size: int) -> tuple[str, str]:
    """Mint a session; return (upload_path, drive_file_id).

    The path is what we PUT against — the stub serves the
    ``/_stub/upload/<id>`` route relative to the same host, so we
    don't need the absolute URL the API returned.
    """
    resp = client.post(
        "/api/drive/initiate-upload",
        json={"file_size_bytes": file_size},
    )
    assert resp.status_code == 200, resp.get_json()
    s = resp.get_json()["sessions"][0]
    # upload_url is absolute (http://localhost/_stub/upload/<id>); the
    # Flask test_client wants a path, so strip the scheme+host.
    path = s["upload_url"].split("://", 1)[1].split("/", 1)[1]
    return "/" + path, s["drive_file_id"]


# ---- unknown ids -----------------------------------------------------


def test_put_to_unknown_id_returns_404(client: FlaskClient) -> None:
    resp = client.put(
        "/_stub/upload/never-minted-id",
        data=b"abc",
        headers={"Content-Range": "bytes 0-2/3"},
    )
    assert resp.status_code == 404
    assert b"unknown upload id" in resp.data


# ---- single-shot path ------------------------------------------------


def test_put_full_file_in_one_chunk_returns_200(client: FlaskClient) -> None:
    upload_path, file_id = _initiate(client, file_size=10)
    resp = client.put(
        upload_path,
        data=b"0123456789",
        headers={"Content-Range": "bytes 0-9/10"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"id": file_id, "webViewLink": None}


def test_put_without_content_range_treated_as_single_shot(
    client: FlaskClient,
) -> None:
    """Phase 1 stub's documented fallback: no Content-Range header
    means "this is the whole thing." The library always sets the
    header in production; this path exists for ad-hoc curl-driven
    smoke tests."""
    upload_path, file_id = _initiate(client, file_size=5)
    resp = client.put(upload_path, data=b"hello")
    assert resp.status_code == 200
    assert resp.get_json() == {"id": file_id, "webViewLink": None}


# ---- multi-chunk path ------------------------------------------------


def test_two_consecutive_partial_puts_close_with_200(
    client: FlaskClient,
) -> None:
    upload_path, file_id = _initiate(client, file_size=200)

    first = client.put(
        upload_path,
        data=b"x" * 100,
        headers={"Content-Range": "bytes 0-99/200"},
    )
    assert first.status_code == 308
    assert first.headers.get("Range") == "bytes=0-99"
    assert first.data == b""  # 308 has no body

    second = client.put(
        upload_path,
        data=b"y" * 100,
        headers={"Content-Range": "bytes 100-199/200"},
    )
    assert second.status_code == 200
    assert second.get_json() == {"id": file_id, "webViewLink": None}


def test_three_chunk_lifecycle_intermediate_range_headers(
    client: FlaskClient,
) -> None:
    """Three sequential chunks of 100 bytes each. Verifies the
    ``Range: bytes=0-N`` header is the cumulative high-water mark on
    each 308, not just the most-recent chunk's end."""
    upload_path, _ = _initiate(client, file_size=300)

    r1 = client.put(
        upload_path, data=b"a" * 100,
        headers={"Content-Range": "bytes 0-99/300"},
    )
    assert r1.status_code == 308
    assert r1.headers.get("Range") == "bytes=0-99"

    r2 = client.put(
        upload_path, data=b"b" * 100,
        headers={"Content-Range": "bytes 100-199/300"},
    )
    assert r2.status_code == 308
    assert r2.headers.get("Range") == "bytes=0-199"

    r3 = client.put(
        upload_path, data=b"c" * 100,
        headers={"Content-Range": "bytes 200-299/300"},
    )
    assert r3.status_code == 200


# ---- out-of-order PUT -----------------------------------------------


def test_out_of_order_put_advances_high_water_mark(
    client: FlaskClient,
) -> None:
    """The stub takes ``max(received, end+1)`` rather than rejecting
    out-of-order ranges. A skip-ahead PUT advances the high-water
    mark to that chunk's end; a follow-up PUT covering the gap is
    accepted but does not move the mark backwards.

    This is intentionally permissive (the stub is a Phase 1 fake);
    the test pins the behaviour so a future change is intentional.
    """
    upload_path, _ = _initiate(client, file_size=300)

    # Skip ahead: send bytes 100-199 first.
    skip = client.put(
        upload_path, data=b"b" * 100,
        headers={"Content-Range": "bytes 100-199/300"},
    )
    assert skip.status_code == 308
    assert skip.headers.get("Range") == "bytes=0-199", (
        "high-water mark should jump to 199 even though bytes 0-99 "
        "were never sent"
    )

    # Backfill bytes 0-99 — the mark must NOT regress.
    backfill = client.put(
        upload_path, data=b"a" * 100,
        headers={"Content-Range": "bytes 0-99/300"},
    )
    assert backfill.status_code == 308
    assert backfill.headers.get("Range") == "bytes=0-199", (
        "max(prev=199, this end+1=100) should pin the mark at 199"
    )

    # Final chunk closes the upload.
    final = client.put(
        upload_path, data=b"c" * 100,
        headers={"Content-Range": "bytes 200-299/300"},
    )
    assert final.status_code == 200


# ---- post-completion access -----------------------------------------


def test_put_after_completion_returns_404(client: FlaskClient) -> None:
    """The session is popped from the in-memory ``_sessions`` dict on
    final 200; subsequent PUTs to the same id are indistinguishable
    from PUTs to an id that never existed."""
    upload_path, _ = _initiate(client, file_size=10)

    first = client.put(
        upload_path, data=b"0123456789",
        headers={"Content-Range": "bytes 0-9/10"},
    )
    assert first.status_code == 200

    again = client.put(
        upload_path, data=b"more bytes",
        headers={"Content-Range": "bytes 10-19/20"},
    )
    assert again.status_code == 404


# ---- Content-Range with `*` total -----------------------------------


def test_content_range_with_star_total_uses_session_size(
    client: FlaskClient,
) -> None:
    """``bytes 0-99/*`` — Drive uses ``*`` when the total is unknown
    yet. The stub falls back to the session's recorded ``size`` (set
    at initiate time)."""
    upload_path, file_id = _initiate(client, file_size=100)

    resp = client.put(
        upload_path, data=b"x" * 100,
        headers={"Content-Range": "bytes 0-99/*"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"id": file_id, "webViewLink": None}
