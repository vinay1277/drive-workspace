"""SpreadsheetLogger + LogSchema protocol.

Per ADR-0004, `LogSchema` is the third plug point: a host declares the
spreadsheet's columns and how to render one row from a host-supplied
payload dict. The package never ships a default `LogSchema` — what
columns belong in the log is inherently a host-domain concern.

The Protocol is intentionally narrow: a list of `ColumnSpec`s and a
`render_row` that maps a payload to a list aligned with those columns.
That's enough for `SpreadsheetLogger` to render the header row when
provisioning a new spreadsheet and to append rows on each event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace


@dataclass(frozen=True)
class ColumnSpec:
    """One spreadsheet column in a host's `LogSchema`.

    `key` is the stable identifier the host uses internally (also matches the
    payload dict key passed to `render_row`); `header` is the human-readable
    text written into row 1 of the spreadsheet at provisioning time.
    """

    key: str
    header: str


class LogSchema(Protocol):
    """Host-supplied: declares spreadsheet columns and renders one row.

    Implementations must guarantee that `render_row(payload)` returns a list
    of the same length as `columns()`, in the same order. `SpreadsheetLogger`
    relies on that invariant to align cells with headers.
    """

    def columns(self) -> list[ColumnSpec]: ...

    def render_row(self, payload: dict[str, Any]) -> list[Any]: ...


class SpreadsheetLogger:
    def __init__(self, dw: DriveWorkspace) -> None:
        self._dw = dw

    def append(self, principal_id: str, row: dict[str, Any]) -> None:
        raise NotImplementedError("Phase 2B")
