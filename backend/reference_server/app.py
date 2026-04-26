"""Reference Flask server — Phase 1 stub.

End-to-end fake: mint a fake session, accept chunked PUTs to a local stub
URL, ack with 308 between chunks and 200 at completion. Zero Drive calls.
"""

from __future__ import annotations

import logging
import re
import secrets
import threading
from typing import Any

from flask import Flask, Response, jsonify, request

logger = logging.getLogger(__name__)

# Per-upload byte-receipt tracking. In-memory because Phase 1 is a single
# worker; Phase 2 replaces this with real Drive resumable sessions.
_lock = threading.Lock()
_sessions: dict[str, dict[str, Any]] = {}

_RANGE_RE = re.compile(r"bytes\s+(\d+)-(\d+)/(\d+|\*)")


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health() -> Response:
        return jsonify({"status": "ok"})

    @app.post("/api/drive/initiate-upload")
    def initiate() -> Response:
        body = request.get_json(silent=True) or {}
        file_size = int(body.get("file_size_bytes", 0))
        upload_id = secrets.token_hex(8)
        with _lock:
            _sessions[upload_id] = {"size": file_size, "received": 0}
        host = request.host_url.rstrip("/")
        return jsonify(
            {
                "upload_url": f"{host}/_stub/upload/{upload_id}",
                "drive_file_id": f"fake-{upload_id}",
                "expires_at": "2099-01-01T00:00:00Z",
            }
        )

    @app.put("/_stub/upload/<upload_id>")
    def stub_upload(upload_id: str) -> Response:
        with _lock:
            session = _sessions.get(upload_id)
        if session is None:
            return Response("unknown upload id", status=404)

        content_range = request.headers.get("Content-Range", "")
        chunk = request.get_data(cache=False)
        match = _RANGE_RE.match(content_range)
        if match:
            end = int(match.group(2))
            total_str = match.group(3)
            total = int(total_str) if total_str != "*" else session["size"]
            received = end + 1
        else:
            # No Content-Range header — treat as full single-shot upload.
            received = len(chunk)
            total = session["size"] or received

        with _lock:
            session["received"] = max(session["received"], received)
            session["size"] = total
            done = session["received"] >= total

        if done:
            with _lock:
                _sessions.pop(upload_id, None)
            return jsonify(
                {
                    "id": f"fake-{upload_id}",
                    "webViewLink": None,
                }
            )

        resp = Response(status=308)
        resp.headers["Range"] = f"bytes=0-{session['received'] - 1}"
        return resp

    return app


app = create_app()
