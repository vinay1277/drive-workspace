"""SmartMeterAuthenticator — wraps drive_workspace's FileAuthenticator
against SmartMeter's secret-storage convention.

Per ADR-0011 the chosen approach is **Shared Drives**, so the SA
credential is loaded from a JSON file unmodified — no DWD ``subject``
plumbing. ``FileAuthenticator`` already does the work; this module
exists to (a) settle the env-var name SmartMeter will use, mirroring
the existing ``GOOGLE_CREDENTIALS_FILE`` / ``GOOGLE_TOKEN_FILE``
convention from ``verticals/google_drive/config.py``, and (b) document
the Shared Drive id env var Phase 2B will start needing.

Env vars SmartMeter sets in production:

    DRIVE_WORKSPACE_SA_KEY_PATH      Absolute or
                                     verticals/gmail/credentials/-relative
                                     path to the SA key JSON.
    DRIVE_WORKSPACE_ROOT_FOLDER_ID   Drive folder id of the per-org
                                     root inside the Shared Drive.
    DRIVE_WORKSPACE_SHARED_DRIVE_ID  Shared Drive id (ADR-0011). Read
                                     by ``DriveWorkspace`` once Phase
                                     2B threads it through; sketched
                                     here so Phase 4 sets the env var
                                     unconditionally.

Falls back to the same default location ``verticals/google_drive``
already uses (``verticals/gmail/credentials/``) so a single
credentials directory continues to be the operational source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path

from drive_workspace.auth import FileAuthenticator

# Mirrors verticals/google_drive/config.py's CREDENTIALS_PATH so
# ops keeps one credentials directory.
_DEFAULT_CREDENTIALS_DIR = Path("verticals/gmail/credentials")
_DEFAULT_SA_KEY_FILENAME = "drive_workspace_sa.json"


def build_authenticator() -> FileAuthenticator:
    """Construct the FileAuthenticator SmartMeter passes to DriveWorkspace.

    Resolution order matches SmartMeter's existing config pattern:

      1. ``DRIVE_WORKSPACE_SA_KEY_PATH`` env var (absolute or relative
         to the working directory).
      2. ``<credentials-dir>/drive_workspace_sa.json`` fallback.

    Raises ``FileNotFoundError`` at construction time if neither path
    resolves to an existing file — same fail-fast behaviour
    ``FileAuthenticator`` provides natively.
    """
    explicit = os.environ.get("DRIVE_WORKSPACE_SA_KEY_PATH")
    if explicit:
        return FileAuthenticator(explicit)
    return FileAuthenticator(_DEFAULT_CREDENTIALS_DIR / _DEFAULT_SA_KEY_FILENAME)


def required_env_vars() -> dict[str, str]:
    """Read the env vars the rest of the SmartMeter glue needs.

    Centralised so the failure mode for a misconfigured deployment is
    one ``KeyError`` at startup, not three different ones across three
    files. Phase 2B may grow this dict (e.g. DWD subject) but for the
    Shared-Drives world chosen by ADR-0011, two ids are enough.
    """
    return {
        "root_folder_id": os.environ["DRIVE_WORKSPACE_ROOT_FOLDER_ID"],
        "shared_drive_id": os.environ["DRIVE_WORKSPACE_SHARED_DRIVE_ID"],
    }
