"""DriveWorkspace — top-level facade. Phase 1 stub."""

from __future__ import annotations

from typing import Any, Protocol

from drive_workspace.folders import FolderManager
from drive_workspace.logs import LogSchema, SpreadsheetLogger
from drive_workspace.reconcile import ReconciliationRunner
from drive_workspace.stores.protocol import PrincipalStore
from drive_workspace.uploads import UploadSessionMint


class Authenticator(Protocol):
    """Returns a Google service-account credential. Host implements.

    Phase 2 will ship a default file-path-backed impl alongside this Protocol.
    """

    def credential(self) -> Any: ...


class DriveWorkspace:
    """Top-level facade aggregating folder, upload, log, and reconcile concerns.

    Phase 1: constructor accepts the documented arguments and exposes the
    sub-managers as attributes; sub-managers raise NotImplementedError.
    """

    def __init__(
        self,
        auth: Authenticator,
        root_folder_id: str,
        shared_drive_id: str,
        template_folder_id: str,
        template_spreadsheet_id: str,
        principal_store: PrincipalStore,
        log_schema: LogSchema,
    ) -> None:
        if not shared_drive_id or not shared_drive_id.strip():
            raise ValueError(
                "shared_drive_id must be a non-empty string "
                "(see ADR-0011: every Drive call needs the Shared Drive id)"
            )
        self.auth = auth
        self.root_folder_id = root_folder_id
        self.shared_drive_id = shared_drive_id
        self.template_folder_id = template_folder_id
        self.template_spreadsheet_id = template_spreadsheet_id
        self.principal_store = principal_store
        self.log_schema = log_schema

        self.principals = FolderManager(self)
        self.uploads = UploadSessionMint(self)
        self.logs = SpreadsheetLogger(self)
        self.reconcile = ReconciliationRunner(self)
