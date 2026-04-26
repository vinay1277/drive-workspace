"""File-backed Authenticator implementation.

The package ships one default `Authenticator` (per ADR-0004): load a Google
service-account JSON key from a filesystem path. Hosts that need env-var or
secret-manager-backed credentials write their own `Authenticator` against
the Protocol declared in `drive_workspace.workspace`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials

# Drive scope: create per-principal folders, share view-only, mint resumable
# upload sessions.
# Sheets scope: append rows to the per-principal log spreadsheet.
SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
)


class FileAuthenticator:
    """Loads a service-account credential from a JSON key file on disk.

    The path is resolved (and existence-checked) at construction time so that
    a misconfigured deployment fails fast at startup rather than on the first
    Drive call. The credential itself is built lazily by `credential()` on
    each call; google-auth handles token refresh internally.
    """

    def __init__(self, key_path: str | Path) -> None:
        resolved = Path(key_path).expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(
                f"Service-account key file not found: {resolved}"
            )
        self._key_path = resolved

    @property
    def key_path(self) -> Path:
        return self._key_path

    def credential(self) -> Any:
        return Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
            str(self._key_path), scopes=list(SCOPES)
        )
