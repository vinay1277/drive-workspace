"""Reference `LogSchema` implementation, used only by tests.

Lives under `tests/_fixtures/` so it's available to tests without polluting
the package's importable surface — `LogSchema` is a host-supplied
plug point and the package intentionally ships no default impl.

Demonstrates the minimal contract: declare columns, then render a row from
a payload dict whose keys match the column keys.
"""

from __future__ import annotations

from typing import Any

from drive_workspace.logs import ColumnSpec


class ExampleLogSchema:
    """timestamp + principal_id + free-text note + photo link.

    The columns chosen here are deliberately generic — this is a fixture
    for testing the Protocol surface, not a template a host should copy.
    """

    _COLUMNS: tuple[ColumnSpec, ...] = (
        ColumnSpec(key="timestamp", header="Timestamp"),
        ColumnSpec(key="principal_id", header="Principal"),
        ColumnSpec(key="note", header="Note"),
        ColumnSpec(key="photo_link", header="Photo"),
    )

    def columns(self) -> list[ColumnSpec]:
        return list(self._COLUMNS)

    def render_row(self, payload: dict[str, Any]) -> list[Any]:
        return [payload.get(col.key) for col in self._COLUMNS]
