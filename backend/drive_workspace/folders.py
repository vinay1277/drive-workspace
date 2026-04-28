"""FolderManager — per-principal folder lifecycle.

Phase 2B: real Drive folder + spreadsheet provisioning. Per ADR-0002,
every principal gets an org-owned folder shared view-only with their
email. Per ADR-0011, all Drive calls pass ``supportsAllDrives=True``
so they target the Shared Drive named by ``DriveWorkspace.shared_drive_id``.

The implementation is intentionally minimal:

  * ``provision`` creates the folder + spreadsheet, writes the header
    row from the host's ``LogSchema.columns()``, optionally shares
    view-only, and persists the mapping. Re-provisioning an existing
    principal updates the persistence row but does NOT recreate the
    Drive folder (Drive's permission model means folder + content
    keep their identity even if the host wants a "clean slate").
  * ``revoke`` drops the principal's view share and records the
    revocation timestamp; files stay in place per ADR-0002.

Lazy provisioning: ``UploadSessionMint.initiate`` calls
``provision_lazy`` when an unknown principal hits the upload endpoint.
That path passes ``display_name = principal_id`` and skips the
``grant_view_to_email`` share (no email is known at upload time).
Hosts that want a custom display name should call ``provision``
explicitly before the first upload.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace

logger = logging.getLogger(__name__)

# Drive MIME type for folders.
_FOLDER_MIME = "application/vnd.google-apps.folder"


class FolderManager:
    """Provision and revoke per-principal Drive folders.

    Exposed as ``DriveWorkspace.principals``. Hosts do not construct
    this class directly.
    """

    def __init__(self, dw: DriveWorkspace) -> None:
        self._dw = dw

    # ------------------------------------------------------------------
    # PUBLIC SURFACE
    # ------------------------------------------------------------------

    def provision(
        self,
        principal_id: str,
        display_name: str,
        grant_view_to_email: str,
    ) -> None:
        """Create the per-principal folder + spreadsheet and persist the mapping.

        Idempotent at the persistence layer: re-provisioning an
        existing principal refreshes the stored ids and clears any
        prior ``revoked_at`` marker. The Drive folder is reused if the
        principal store already records one — only freshly-unknown
        principals trigger a folder create.

        Args:
            principal_id: Stable identifier for the principal.
            display_name: Human-readable name for the folder.
            grant_view_to_email: Google account email shared view-only.
                Pass an empty string to skip the share (lazy-provision
                path uses this).
        """
        existing_folder_id = self._dw.principal_store.get_folder_id(principal_id)
        existing_sheet_id = self._dw.principal_store.get_spreadsheet_id(principal_id)

        if existing_folder_id and existing_sheet_id:
            # Already provisioned — refresh the persistence row to
            # clear any prior revocation, but don't churn Drive.
            self._dw.principal_store.record_provisioned(
                principal_id, existing_folder_id, existing_sheet_id
            )
            if grant_view_to_email:
                self._share_view(existing_folder_id, grant_view_to_email)
            return

        drive = self._drive()
        sheets = self._sheets()

        folder_id = existing_folder_id or self._create_folder(
            drive=drive,
            name=display_name or principal_id,
            parent_id=self._dw.root_folder_id,
        )

        sheet_id = existing_sheet_id or self._create_log_sheet(
            drive=drive,
            sheets=sheets,
            parent_id=folder_id,
        )

        if grant_view_to_email:
            self._share_view(folder_id, grant_view_to_email)

        self._dw.principal_store.record_provisioned(principal_id, folder_id, sheet_id)
        logger.info(
            "drive_workspace.provision: principal=%s folder=%s sheet=%s",
            principal_id, folder_id, sheet_id,
        )

    def revoke(self, principal_id: str) -> None:
        """Drop the principal's share on the folder; leave files intact."""
        folder_id = self._dw.principal_store.get_folder_id(principal_id)
        if not folder_id:
            self._dw.principal_store.record_revoked(principal_id)
            return

        # Best-effort: drop any non-owner permissions that look like a
        # principal grant. The org/SA permissions stay.
        drive = self._drive()
        try:
            permissions = drive.permissions().list(
                fileId=folder_id,
                fields="permissions(id,type,emailAddress,role)",
                supportsAllDrives=True,
            ).execute().get("permissions", [])
            for perm in permissions:
                if perm.get("role") == "reader" and perm.get("type") == "user":
                    drive.permissions().delete(
                        fileId=folder_id,
                        permissionId=perm["id"],
                        supportsAllDrives=True,
                    ).execute()
        except Exception:
            logger.warning(
                "drive_workspace.revoke: best-effort permission cleanup failed for %s",
                principal_id, exc_info=True,
            )

        self._dw.principal_store.record_revoked(principal_id)
        logger.info("drive_workspace.revoke: principal=%s", principal_id)

    # ------------------------------------------------------------------
    # INTERNAL — used by UploadSessionMint for lazy-provision
    # ------------------------------------------------------------------

    def provision_lazy(self, principal_id: str) -> str:
        """Provision with defaults if missing; return the folder_id.

        Called from ``UploadSessionMint.initiate`` when a fresh
        principal hits the upload endpoint without a prior
        ``provision`` call. Skips the email share (no email known)
        and uses the principal_id as the display name.
        """
        folder_id = self._dw.principal_store.get_folder_id(principal_id)
        if folder_id:
            return folder_id

        self.provision(
            principal_id=principal_id,
            display_name=principal_id,
            grant_view_to_email="",
        )
        result = self._dw.principal_store.get_folder_id(principal_id)
        if not result:
            raise RuntimeError(
                f"provision_lazy({principal_id}) completed but principal_store "
                f"still has no folder_id"
            )
        return result

    # ------------------------------------------------------------------
    # DRIVE / SHEETS HELPERS
    # ------------------------------------------------------------------

    def _drive(self) -> Any:
        from googleapiclient.discovery import build
        return build("drive", "v3", credentials=self._dw.auth.credential(), cache_discovery=False)

    def _sheets(self) -> Any:
        from googleapiclient.discovery import build
        return build("sheets", "v4", credentials=self._dw.auth.credential(), cache_discovery=False)

    def _create_folder(self, drive: Any, name: str, parent_id: str) -> str:
        """Create a folder under parent_id; return its id.

        Idempotency: if a folder with the same name already exists
        under parent_id (in the Shared Drive scope), reuse it. This
        keeps re-provisioning safe.
        """
        existing = self._find_child(
            drive, parent_id=parent_id, name=name, mime_type=_FOLDER_MIME,
        )
        if existing:
            return existing

        created = drive.files().create(
            body={
                "name": name,
                "mimeType": _FOLDER_MIME,
                "parents": [parent_id],
            },
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return str(created["id"])

    def _create_log_sheet(self, drive: Any, sheets: Any, parent_id: str) -> str:
        """Create the per-principal log spreadsheet inside parent_id.

        Writes the header row from ``dw.log_schema.columns()``. Idempotent:
        a Sheet named ``log`` already inside parent_id is reused.
        """
        sheet_mime = "application/vnd.google-apps.spreadsheet"
        existing = self._find_child(
            drive, parent_id=parent_id, name="log", mime_type=sheet_mime,
        )
        if existing:
            return existing

        created = drive.files().create(
            body={
                "name": "log",
                "mimeType": sheet_mime,
                "parents": [parent_id],
            },
            fields="id",
            supportsAllDrives=True,
        ).execute()
        sheet_id = str(created["id"])

        # Write the header row from the host's LogSchema.
        try:
            specs = self._dw.log_schema.columns()
        except Exception:
            specs = []
        if specs:
            header = [spec.header for spec in specs]
            sheets.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="A1",
                valueInputOption="USER_ENTERED",
                body={"values": [header]},
            ).execute()

        return sheet_id

    def _find_child(
        self,
        drive: Any,
        *,
        parent_id: str,
        name: str,
        mime_type: str,
    ) -> str | None:
        """Return the id of the named child under parent_id or None."""
        # Escape single quotes in name for the Drive query syntax.
        safe_name = name.replace("'", r"\'")
        res = drive.files().list(
            q=(
                f"'{parent_id}' in parents and "
                f"name='{safe_name}' and "
                f"mimeType='{mime_type}' and trashed=false"
            ),
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="drive",
            driveId=self._dw.shared_drive_id,
        ).execute()
        files = res.get("files", [])
        return str(files[0]["id"]) if files else None

    def _share_view(self, file_id: str, email: str) -> None:
        """Grant the principal view-only access to file_id."""
        drive = self._drive()
        try:
            drive.permissions().create(
                fileId=file_id,
                body={
                    "type": "user",
                    "role": "reader",
                    "emailAddress": email,
                },
                supportsAllDrives=True,
                sendNotificationEmail=False,
            ).execute()
        except Exception:
            logger.warning(
                "drive_workspace._share_view: share to %s on %s failed",
                email, file_id, exc_info=True,
            )
