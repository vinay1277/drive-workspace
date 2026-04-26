"""SpreadsheetLogger + LogSchema protocol. Phase 1 stub."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace


class LogSchema(Protocol):
    """Host-supplied: declares spreadsheet columns and renders one row."""

    def columns(self) -> list[str]: ...

    def render_row(self, payload: dict[str, Any]) -> list[Any]: ...


class SpreadsheetLogger:
    def __init__(self, dw: DriveWorkspace) -> None:
        self._dw = dw

    def append(self, principal_id: str, row: dict[str, Any]) -> None:
        raise NotImplementedError("Phase 2")
