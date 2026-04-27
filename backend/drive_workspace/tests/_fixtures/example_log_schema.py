"""Reference `LogSchema` implementation, used only by tests.

Lives under `tests/_fixtures/` so it's available to tests without polluting
the package's importable surface — `LogSchema` is a host-supplied
plug point and the package intentionally ships no default impl.

Demonstrates the minimal contract: declare columns, then render a row from
a payload dict whose keys match the column keys. Also demonstrates the
recommended **TypedDict pattern** — hosts SHOULD declare the payload shape
they expect so mypy catches missing or misspelled keys at every call site,
not at runtime when the row renders ``None`` for a typo'd key.
"""

from __future__ import annotations

from typing import Any, TypedDict

from drive_workspace.logs import ColumnSpec


class ExampleLogPayload(TypedDict, total=False):
    """Payload shape ExampleLogSchema accepts.

    All keys are optional (``total=False``) because the example schema's
    ``render_row`` is permissive — missing keys become ``None`` cells.
    Hosts that want strict payloads should declare ``total=True`` and
    require every key.
    """

    timestamp: str
    principal_id: str
    note: str
    photo_link: str


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
        # Hosts call as: schema.render_row(cast(dict, my_payload))
        # where my_payload: ExampleLogPayload. mypy enforces the TypedDict
        # at the host call site; the package signature stays generic.
        return [payload.get(col.key) for col in self._COLUMNS]
