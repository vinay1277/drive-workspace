"""DriveWorkspace — top-level facade.

Phase 1 stub: the constructor accepts the documented arguments
and exposes the sub-managers (``principals``, ``uploads``, ``logs``,
``reconcile``) as attributes. The sub-managers' methods raise
``NotImplementedError`` until Phase 2B wires them up.
"""

from __future__ import annotations

from typing import Any, Protocol

from drive_workspace.folders import FolderManager
from drive_workspace.logs import LogSchema, SpreadsheetLogger
from drive_workspace.reconcile import ReconciliationRunner
from drive_workspace.stores.protocol import PrincipalStore
from drive_workspace.uploads import UploadSessionMint


class Authenticator(Protocol):
    """Plug point: return a Google service-account ``Credentials``.

    Per ADR-0004 the host implements this Protocol; the default
    file-path impl ships as ``drive_workspace.auth.FileAuthenticator``.
    Hosts that need an env-var, callable, or secret-manager-backed
    credential write their own against this interface.
    """

    def credential(self) -> Any:
        """Return a fresh ``google.oauth2.service_account.Credentials``.

        Implementations may return a cached credential; ``google-auth``
        handles token refresh internally.
        """
        ...


class DriveWorkspace:
    """Top-level facade aggregating folder, upload, log, and reconcile concerns.

    Hosts construct one ``DriveWorkspace`` at app boot and use the
    sub-manager attributes for every operation:

    - ``principals`` (``FolderManager``): provision / revoke per-principal folders.
    - ``uploads`` (``UploadSessionMint``): mint resumable upload sessions.
    - ``logs`` (``SpreadsheetLogger``): append rows to the per-principal spreadsheet.
    - ``reconcile`` (``ReconciliationRunner``): orphan detection / cleanup.

    Args:
        auth: Authenticator that returns the SA credential.
        root_folder_id: Drive folder id at the root of the
            per-principal subtree (folder lives *inside* the Shared
            Drive named by ``shared_drive_id``).
        shared_drive_id: Drive Shared Drive id (per ADR-0011). All
            ``drive_workspace`` content lives inside this Shared
            Drive; every Drive API call passes
            ``supportsAllDrives=True``. Validated non-empty at
            construction; raises ``ValueError`` otherwise.
        template_folder_id: Folder id of the per-principal template
            subtree (copied at provision time).
        template_spreadsheet_id: Spreadsheet id of the per-principal
            log template (copied at provision time).
        principal_store: Host-supplied ``PrincipalStore`` impl.
        log_schema: Host-supplied ``LogSchema`` impl.

    Raises:
        ValueError: If ``shared_drive_id`` is empty or whitespace.

    Attributes:
        auth: The ``Authenticator`` passed in.
        root_folder_id: As above.
        shared_drive_id: As above.
        template_folder_id: As above.
        template_spreadsheet_id: As above.
        principal_store: The host's ``PrincipalStore``.
        log_schema: The host's ``LogSchema``.
        principals: ``FolderManager`` bound to this workspace.
        uploads: ``UploadSessionMint`` bound to this workspace.
        logs: ``SpreadsheetLogger`` bound to this workspace.
        reconcile: ``ReconciliationRunner`` bound to this workspace.
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
