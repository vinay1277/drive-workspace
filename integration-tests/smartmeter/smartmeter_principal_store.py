"""SmartMeterPrincipalStore — drive_workspace.PrincipalStore impl backed by
SmartMeter's existing ``surveyors`` table.

ADR-0004 says the host wraps its existing user table; this is that
wrapper for SmartMeter. ``surveyor_id`` (the BIGINT PK on the
``SmartMeter.surveyors`` table from migration ``035_surveyors_table.sql``)
is the natural ``principal_id``. The Drive folder/spreadsheet IDs get
added as new columns; the docstring below carries the migration SQL
SmartMeter will run when Phase 4 ships.

This is a **sketch**: nothing here imports SmartMeter for real. The
``DatabaseManager`` import is type-ignored; in production the real
``core.database_manager.DatabaseManager`` is dropped in unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Real import in production:
    #   from core.database_manager import DatabaseManager
    # The sketch declares a structural type so mypy --strict has
    # something to check the call sites against without depending on
    # SmartMeter being installed.
    class DatabaseManager:
        def execute_query(
            self,
            sql: str,
            params: tuple[Any, ...] | dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]: ...


# -----------------------------------------------------------------------------
# Migration SmartMeter must run when Phase 4 lands. Mirrors the revision
# pattern of the surveyors table — these columns live on the *current*
# revision row only, so no extra revision bookkeeping is needed beyond
# what surveyors already has.
#
#   ALTER TABLE SmartMeter.surveyors
#       ADD COLUMN drive_folder_id      VARCHAR(64) NULL
#                  COMMENT 'Per-principal Drive folder (drive_workspace).',
#       ADD COLUMN drive_spreadsheet_id VARCHAR(64) NULL
#                  COMMENT 'Per-principal log spreadsheet (drive_workspace).',
#       ADD COLUMN drive_provisioned_at TIMESTAMP   NULL,
#       ADD COLUMN drive_revoked_at     TIMESTAMP   NULL,
#       ADD INDEX idx_drive_folder (drive_folder_id);
#
# Backfill: existing surveyors are NULL on the new columns; Phase 4
# rollout calls ``provision()`` per-active-surveyor lazily on first
# upload (or via a one-shot script — see README "Migration notes").
# -----------------------------------------------------------------------------


class SmartMeterPrincipalStore:
    """``PrincipalStore`` Protocol impl backed by ``SmartMeter.surveyors``.

    Reads/writes only the four ``drive_*`` columns added by the
    migration above. Identity is the *current-revision* surveyor row
    keyed by ``surveyor_id`` (cast to ``str`` because drive_workspace's
    Protocol uses ``str`` principal ids; SmartMeter's PK is BIGINT —
    cast at the boundary, never inside the package).
    """

    def __init__(self, db: DatabaseManager, db_name: str = "SmartMeter") -> None:
        self._db = db
        self._db_name = db_name

    def get_folder_id(self, principal_id: str) -> str | None:
        rows = self._db.execute_query(
            f"""
            SELECT drive_folder_id
              FROM {self._db_name}.surveyors
             WHERE surveyor_id = %s
               AND is_current_revision = 'Y'
               AND active = 'Y'
               AND drive_revoked_at IS NULL
            """,
            (int(principal_id),),
        )
        if not rows:
            return None
        folder_id = rows[0].get("drive_folder_id")
        return folder_id if isinstance(folder_id, str) and folder_id else None

    def get_spreadsheet_id(self, principal_id: str) -> str | None:
        rows = self._db.execute_query(
            f"""
            SELECT drive_spreadsheet_id
              FROM {self._db_name}.surveyors
             WHERE surveyor_id = %s
               AND is_current_revision = 'Y'
               AND active = 'Y'
               AND drive_revoked_at IS NULL
            """,
            (int(principal_id),),
        )
        if not rows:
            return None
        sheet_id = rows[0].get("drive_spreadsheet_id")
        return sheet_id if isinstance(sheet_id, str) and sheet_id else None

    def record_provisioned(
        self,
        principal_id: str,
        folder_id: str,
        spreadsheet_id: str,
    ) -> None:
        self._db.execute_query(
            f"""
            UPDATE {self._db_name}.surveyors
               SET drive_folder_id      = %s,
                   drive_spreadsheet_id = %s,
                   drive_provisioned_at = COALESCE(drive_provisioned_at, NOW()),
                   drive_revoked_at     = NULL
             WHERE surveyor_id = %s
               AND is_current_revision = 'Y'
               AND active = 'Y'
            """,
            (folder_id, spreadsheet_id, int(principal_id)),
        )

    def record_revoked(self, principal_id: str) -> None:
        # Drop the share at the Drive layer (FolderManager.revoke handles
        # that side); locally we just mark the row revoked. Re-provisioning
        # later writes a new pair of ids and clears drive_revoked_at, per
        # the SqlAlchemy reference impl's contract.
        self._db.execute_query(
            f"""
            UPDATE {self._db_name}.surveyors
               SET drive_revoked_at = NOW()
             WHERE surveyor_id = %s
               AND is_current_revision = 'Y'
               AND active = 'Y'
            """,
            (int(principal_id),),
        )
