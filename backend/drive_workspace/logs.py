"""SpreadsheetLogger + LogSchema protocol.

Per ADR-0004, ``LogSchema`` is the third plug point: a host
declares the spreadsheet's columns and how to render one row from
a host-supplied payload dict. The package never ships a default
``LogSchema`` — what columns belong in the log is inherently a
host-domain concern.

The Protocol is intentionally narrow: a list of ``ColumnSpec`` and
a ``render_row`` that maps a payload to a list aligned with those
columns. That's enough for ``SpreadsheetLogger`` to render the
header row when provisioning a new spreadsheet and to append rows
on each event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace


@dataclass(frozen=True)
class ColumnSpec:
    """One spreadsheet column in a host's ``LogSchema``.

    Attributes:
        key: Stable identifier the host uses internally; also the
            payload dict key passed to ``LogSchema.render_row``.
        header: Human-readable text written into row 1 of the
            spreadsheet at provisioning time.
    """

    key: str
    header: str


class LogSchema(Protocol):
    """Plug point: declare spreadsheet columns and render one row.

    Implementations must guarantee that ``render_row(payload)``
    returns a list of the same length as ``columns()``, in the same
    order. ``SpreadsheetLogger`` relies on that invariant to align
    cells with headers at append time.
    """

    def columns(self) -> list[ColumnSpec]:
        """Return the spreadsheet's columns, header-row order.

        Called once per spreadsheet provisioning to write the
        header row; the order is the contract that
        ``render_row`` honours on every subsequent append.
        """
        ...

    def render_row(self, payload: dict[str, Any]) -> list[Any]:
        """Render one spreadsheet row from a host-supplied payload.

        Args:
            payload: Host-defined dict; the keys it must carry are
                the host's contract with itself — typically
                ``ColumnSpec.key`` for each column, plus any extra
                ids the host needs for HYPERLINK rendering.

        Returns:
            A list of cell values aligned with ``columns()`` order.
            Cells may be primitives, formula strings (e.g.
            ``=HYPERLINK(...)``), or ``None``.
        """
        ...


class SpreadsheetLogger:
    """Append rows to per-principal log spreadsheets.

    Exposed as ``DriveWorkspace.logs``. Phase 2B wires this to the
    Sheets ``values.append`` API; the per-principal spreadsheet id
    is resolved via ``DriveWorkspace.principal_store.get_spreadsheet_id``.
    """

    def __init__(self, dw: DriveWorkspace) -> None:
        self._dw = dw

    def append(self, principal_id: str, row: dict[str, Any]) -> None:
        """Append one row to the principal's log spreadsheet.

        Args:
            principal_id: Stable identifier; must already be
                provisioned (``get_spreadsheet_id`` non-None).
            row: Payload passed straight through to the host's
                ``LogSchema.render_row``.

        Raises:
            NotImplementedError: Phase 1 stub.
        """
        raise NotImplementedError("Phase 2B")
