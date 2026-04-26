"""FolderManager — per-principal folder lifecycle.

Phase 1 stub: the public surface is locked but the methods raise
``NotImplementedError``. Phase 2B fills in the Drive-side work
(create folder from template, share view-only, persist mapping via
``PrincipalStore``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace


class FolderManager:
    """Provision and revoke per-principal Drive folders.

    Per ADR-0002, every principal gets an org-owned folder shared
    view-only with their email. ``provision`` creates the folder
    (copied from the template subtree at
    ``DriveWorkspace.template_folder_id``) and a per-principal log
    spreadsheet (copied from
    ``DriveWorkspace.template_spreadsheet_id``), shares the folder
    with the principal, and persists the resulting ids via
    ``DriveWorkspace.principal_store``. ``revoke`` drops the share
    but leaves the files in place so the org retains chain of
    custody.

    Exposed as ``DriveWorkspace.principals``. Hosts do not construct
    this class directly.
    """

    def __init__(self, dw: DriveWorkspace) -> None:
        self._dw = dw

    def provision(
        self,
        principal_id: str,
        display_name: str,
        grant_view_to_email: str,
    ) -> None:
        """Create the per-principal folder + spreadsheet and persist the mapping.

        Idempotent at the persistence layer: re-provisioning an
        existing principal refreshes the stored ids and clears any
        prior ``revoked_at`` marker (per the
        ``SqlAlchemyPrincipalStore.record_provisioned`` contract).
        Whether the underlying Drive folder is recreated or reused
        is a Phase 2B implementation choice.

        Args:
            principal_id: Stable identifier for the principal.
                Hosts typically use their existing user-table primary
                key cast to ``str``.
            display_name: Human-readable name for the folder
                (e.g. ``"Alice Example"``); used in the Drive UI.
            grant_view_to_email: Google account email the per-principal
                folder is shared with as Viewer. May be a personal
                Gmail; per ADR-0011, the org's Shared Drive must
                allow external-member sharing.

        Raises:
            NotImplementedError: Phase 1 stub.
        """
        raise NotImplementedError("Phase 2")

    def revoke(self, principal_id: str) -> None:
        """Drop the principal's share on the folder; leave files intact.

        Per ADR-0002 the org retains every byte; revoke is a single
        Drive ACL change plus a ``record_revoked`` call into the
        principal store. The folder and its contents stay in place
        so the chain of custody is preserved.

        Args:
            principal_id: Same identifier used when ``provision``
                was called. Unknown ids are a no-op rather than an
                error (matches ``SqlAlchemyPrincipalStore.record_revoked``).

        Raises:
            NotImplementedError: Phase 1 stub.
        """
        raise NotImplementedError("Phase 2")
