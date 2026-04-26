"""Unit tests for DriveWorkspace constructor — shared_drive_id validation.

Per ADR-0011, every Drive API call must carry the Shared Drive id; the
constructor rejects empty values fail-fast at startup, matching the
posture FileAuthenticator uses for missing key files.
"""

from __future__ import annotations

from typing import Any

import pytest

from drive_workspace import (
    ColumnSpec,
    DriveWorkspace,
    LogSchema,
)
from drive_workspace.stores.protocol import PrincipalStore


class _FakeAuth:
    def credential(self) -> Any:
        return None


class _FakePrincipalStore:
    def get_folder_id(self, principal_id: str) -> str | None:
        return None

    def get_spreadsheet_id(self, principal_id: str) -> str | None:
        return None

    def record_provisioned(
        self, principal_id: str, folder_id: str, spreadsheet_id: str
    ) -> None: ...

    def record_revoked(self, principal_id: str) -> None: ...


class _FakeLogSchema:
    def columns(self) -> list[ColumnSpec]:
        return [ColumnSpec(key="ts", header="Timestamp")]

    def render_row(self, payload: dict[str, Any]) -> list[Any]:
        return [payload.get("ts")]


def _build(shared_drive_id: str) -> DriveWorkspace:
    store: PrincipalStore = _FakePrincipalStore()
    schema: LogSchema = _FakeLogSchema()
    return DriveWorkspace(
        auth=_FakeAuth(),
        root_folder_id="root-1",
        shared_drive_id=shared_drive_id,
        template_folder_id="tpl-folder",
        template_spreadsheet_id="tpl-sheet",
        principal_store=store,
        log_schema=schema,
    )


def test_shared_drive_id_stored_as_attribute() -> None:
    dw = _build("0AB-shared-drive")
    assert dw.shared_drive_id == "0AB-shared-drive"


@pytest.mark.parametrize("bad", ["", " ", "\t", "\n", "   "])
def test_empty_or_whitespace_shared_drive_id_raises(bad: str) -> None:
    with pytest.raises(ValueError, match="shared_drive_id"):
        _build(bad)
