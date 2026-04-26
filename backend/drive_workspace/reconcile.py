"""ReconciliationRunner — orphan detection and cleanup. Phase 1 stub."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace


class ReconciliationRunner:
    def __init__(self, dw: DriveWorkspace) -> None:
        self._dw = dw

    def run(self) -> None:
        raise NotImplementedError("Phase 2")
