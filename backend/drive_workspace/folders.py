"""FolderManager — per-principal folder lifecycle. Phase 1 stub."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace


class FolderManager:
    def __init__(self, dw: DriveWorkspace) -> None:
        self._dw = dw

    def provision(
        self,
        principal_id: str,
        display_name: str,
        grant_view_to_email: str,
    ) -> None:
        raise NotImplementedError("Phase 2")

    def revoke(self, principal_id: str) -> None:
        raise NotImplementedError("Phase 2")
