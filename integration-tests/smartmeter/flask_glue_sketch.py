"""Flask glue sketch — what SmartMeter's ``app.py`` adds when Phase 4
lands.

This file does not run. It imports drive_workspace types, hand-wires
two routes the way SmartMeter's existing verticals do, and commits to
``core.surveyor_auth.require_surveyor_auth`` as the authentication
decorator. The latter import is type-ignored here because
drive_workspace must not depend on SmartMeter; in production SmartMeter
imports its own decorator unchanged.

``drive_workspace.adapters.flask.make_blueprint`` does **not exist
yet** (Phase 2A left ``adapters/flask.py`` as a one-line stub). This
sketch hand-wires the routes; once Phase 2B ships ``make_blueprint``,
SmartMeter swaps roughly half of this file for a one-line invocation.
That gap is the most concrete actionable finding of the dry run; see
``README.md`` and the ``plan.md`` task added under "Open work outside
the phase plan".
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Flask, jsonify, request

from drive_workspace import (
    DriveWorkspace,
    FileSpec,
)

from .smartmeter_authenticator import build_authenticator, required_env_vars
from .smartmeter_log_schema import SmartMeterLogSchema
from .smartmeter_principal_store import SmartMeterPrincipalStore

# -----------------------------------------------------------------------------
# SmartMeter imports — referenced via type comments only so this file
# imports cleanly under a venv that has drive_workspace but not
# SmartMeter. In production, replace these stubs with:
#
#     from core.database_manager import DatabaseManager
#     from core.surveyor_auth import require_surveyor_auth, get_surveyor_context
# -----------------------------------------------------------------------------


def _placeholder_db() -> Any:
    """Stand-in for ``DatabaseManager()``. Production drops in the real one."""
    raise RuntimeError(
        "smartmeter integration sketch — wire core.database_manager.DatabaseManager() here",
    )


def _placeholder_require_surveyor_auth(fn: Any) -> Any:
    """Stand-in for SmartMeter's JWT decorator. Real decorator validates the
    Bearer token, resolves surveyor/device/binding, and stashes them in
    ``flask.g``; ``get_surveyor_context()`` exposes them to handlers."""
    return fn


def _placeholder_get_surveyor_context() -> dict[str, Any]:
    """Stand-in for ``core.surveyor_auth.get_surveyor_context``. Returns
    the JWT-resolved surveyor context: ``surveyor_id`` (BIGINT),
    ``device_uuid``, ``binding_id``, ``employee_code``."""
    return {"surveyor_id": 0, "device_uuid": "", "binding_id": 0, "employee_code": ""}


# -----------------------------------------------------------------------------
# Application wiring. SmartMeter's ``app.py`` calls ``register_drive_workspace``
# once on boot, passing in the live Flask app and the live DatabaseManager.
# Everything else is local construction.
# -----------------------------------------------------------------------------


def build_drive_workspace() -> DriveWorkspace:
    """Wire drive_workspace once on app boot. The returned object is
    process-local; share via Flask app context or a module-level global."""
    env = required_env_vars()
    return DriveWorkspace(
        auth=build_authenticator(),
        root_folder_id=env["root_folder_id"],
        # Phase 2B threads shared_drive_id through DriveWorkspace; for now
        # the env var is captured by required_env_vars() and the constructor
        # ignores it. Sketch flagged this in README "Gaps".
        template_folder_id="<from app_configuration: drive_workspace_template_folder_id>",
        template_spreadsheet_id="<from app_configuration: drive_workspace_template_spreadsheet_id>",
        principal_store=SmartMeterPrincipalStore(_placeholder_db()),
        log_schema=SmartMeterLogSchema(),
    )


def register_drive_workspace(app: Flask, dw: DriveWorkspace) -> None:
    """Mount the two surveyor-facing endpoints onto an existing Flask app.

    These hand-wired routes go away once
    ``drive_workspace.adapters.flask.make_blueprint(dw, auth_decorator)``
    ships in Phase 2B. The contract that survives the swap is the
    URL prefix ``/api/drive/`` and the JSON shapes documented in
    ``docs/BACKEND_CONTRACT.md``.
    """
    bp = Blueprint("drive_workspace", __name__, url_prefix="/api/drive")

    @bp.post("/initiate-upload")
    @_placeholder_require_surveyor_auth
    def initiate_upload() -> Any:
        ctx = _placeholder_get_surveyor_context()
        body = request.get_json(silent=True) or {}
        count = max(1, int(request.args.get("count", "1")))

        # Build N FileSpecs from one template; ADR-0003 prefetch passes
        # count > 1, the synchronous upload path passes 1.
        spec = FileSpec(
            file_name=body.get("file_name", "upload"),
            mime_type=body.get("mime_type", "application/octet-stream"),
            file_size_bytes=int(body.get("file_size_bytes", 0) or 1),
            kind=body.get("kind_hint") or "photo",
        )
        sessions = dw.uploads.initiate(
            principal_id=str(ctx["surveyor_id"]),
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
    @_placeholder_require_surveyor_auth
    def record_submission() -> Any:
        """SmartMeter's existing survey-submission endpoint, augmented
        to log a row into the per-principal spreadsheet. The host's
        existing storage of the submission (in its own tables) is
        unchanged; this just appends one row."""
        ctx = _placeholder_get_surveyor_context()
        payload = request.get_json(silent=False) or {}
        dw.logs.append(
            principal_id=str(ctx["surveyor_id"]),
            row=payload,
        )
        return jsonify({"ok": True})

    app.register_blueprint(bp)
