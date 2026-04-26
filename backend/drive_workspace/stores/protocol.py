"""PrincipalStore protocol — host-supplied persistence plug point.

Per ADR-0004: structural Protocol, no inheritance required. Host
wraps its existing user table in ~30 lines.
"""

from __future__ import annotations

from typing import Protocol


class PrincipalStore(Protocol):
    """Plug point: persist ``(principal_id → folder_id, spreadsheet_id)`` mappings.

    Default impl ships as
    ``drive_workspace.stores.sqlalchemy.SqlAlchemyPrincipalStore``.
    Hosts on a non-SQL persistence layer write their own against
    this Protocol; structural typing means no inheritance is
    required.
    """

    def get_folder_id(self, principal_id: str) -> str | None:
        """Return the principal's Drive folder id, or ``None`` if not provisioned.

        Revoked principals must return ``None`` (the package treats
        a revoked mapping the same as a missing one).
        """
        ...

    def get_spreadsheet_id(self, principal_id: str) -> str | None:
        """Return the principal's log-spreadsheet id, or ``None`` if not provisioned.

        Same revoked-as-missing semantics as ``get_folder_id``.
        """
        ...

    def record_provisioned(
        self,
        principal_id: str,
        folder_id: str,
        spreadsheet_id: str,
    ) -> None:
        """Record (or refresh) a principal's folder + spreadsheet ids.

        Idempotent: re-provisioning an existing principal updates
        the ids and clears any prior revoked marker.
        """
        ...

    def record_revoked(self, principal_id: str) -> None:
        """Mark a principal as revoked. No-op for unknown ids."""
        ...
