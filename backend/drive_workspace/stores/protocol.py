"""PrincipalStore protocol — host-supplied persistence plug point.

Per ADR-0004: structural Protocol, no inheritance required. Host wraps its
existing user table in ~30 lines.
"""

from __future__ import annotations

from typing import Protocol


class PrincipalStore(Protocol):
    def get_folder_id(self, principal_id: str) -> str | None: ...

    def get_spreadsheet_id(self, principal_id: str) -> str | None: ...

    def record_provisioned(
        self,
        principal_id: str,
        folder_id: str,
        spreadsheet_id: str,
    ) -> None: ...

    def record_revoked(self, principal_id: str) -> None: ...
