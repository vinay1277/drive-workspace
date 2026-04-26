"""Flask glue sketch — what SmartMeter's ``app.py`` adds when Phase 4
lands.

This file does not run. It imports drive_workspace types and shows
the production wiring: build a ``DriveWorkspace`` once on boot, then
mount ``drive_workspace.adapters.flask.make_blueprint(...)`` under
the host's auth decorator. The auth decorator is type-ignored here
because drive_workspace must not depend on SmartMeter; in production
SmartMeter imports its own decorator unchanged.

Per ADR-0011 the constructor takes ``shared_drive_id``; the env-var
plumbing lives in ``smartmeter_authenticator.required_env_vars()``.

The blueprint contract (per
``drive_workspace/adapters/flask.py``) is that the host's auth
decorator sets ``flask.g.principal_id: str`` before the view runs.
SmartMeter's ``core.surveyor_auth.require_surveyor_auth`` already
populates ``flask.g`` with the surveyor context; the production hook
sets ``g.principal_id = str(g.surveyor_id)`` inside (or alongside)
that decorator. The placeholder here is a no-op decorator that sets
``g.principal_id = "0"`` so this sketch type-checks without
SmartMeter on the path.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from flask import Flask, g

from drive_workspace import DriveWorkspace
from drive_workspace.adapters.flask import make_blueprint

from .smartmeter_authenticator import build_authenticator, required_env_vars
from .smartmeter_log_schema import SmartMeterLogSchema
from .smartmeter_principal_store import SmartMeterPrincipalStore

F = TypeVar("F", bound=Callable[..., Any])


def _placeholder_db() -> Any:
    """Stand-in for ``DatabaseManager()``. Production drops in the real one."""
    raise RuntimeError(
        "smartmeter integration sketch — wire core.database_manager.DatabaseManager() here",
    )


def _placeholder_require_principal_auth(view: F) -> F:
    """Stand-in for SmartMeter's JWT decorator.

    Production replaces with ``core.surveyor_auth.require_surveyor_auth``
    augmented to set ``g.principal_id = str(g.surveyor_id)`` (or moves
    that one-liner into the existing decorator). The blueprint contract
    is just ``flask.g.principal_id: str`` — how SmartMeter resolves the
    JWT is unchanged.
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        g.principal_id = "0"
        return view(*args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper  # type: ignore[return-value]


def build_drive_workspace() -> DriveWorkspace:
    """Wire drive_workspace once on app boot. The returned object is
    process-local; share via Flask app context or a module-level global."""
    env = required_env_vars()
    return DriveWorkspace(
        auth=build_authenticator(),
        root_folder_id=env["root_folder_id"],
        shared_drive_id=env["shared_drive_id"],
        template_folder_id="<from app_configuration: drive_workspace_template_folder_id>",
        template_spreadsheet_id="<from app_configuration: drive_workspace_template_spreadsheet_id>",
        principal_store=SmartMeterPrincipalStore(_placeholder_db()),
        log_schema=SmartMeterLogSchema(),
    )


def register_drive_workspace(app: Flask, dw: DriveWorkspace) -> None:
    """Mount the surveyor-facing endpoints onto an existing Flask app.

    One ``register_blueprint`` call replaces what was ~50 lines of
    hand-wired routes before ``make_blueprint`` shipped. The wire
    contract (URL paths, JSON shapes) lives in
    ``docs/BACKEND_CONTRACT.md`` and ``drive_workspace.adapters.flask``.
    """
    app.register_blueprint(
        make_blueprint(dw, auth_decorator=_placeholder_require_principal_auth)
    )
