"""SQL helpers for hosts adding ``drive_workspace`` to an existing user table.

When a host integrates ``drive_workspace`` with an existing ``users``-style
table (rather than using the default ``SqlAlchemyPrincipalStore`` and its
own ``drive_workspace_principals`` table), the host typically wants to add
``drive_folder_id`` and ``drive_spreadsheet_id`` columns to the existing
table — wiring its own ``PrincipalStore`` impl to read/write those columns.

The actual ``ALTER TABLE`` SQL is small but tedious: column nullability,
quoting conventions, vendor-specific syntax. This module returns the SQL
as a string the host can run via its preferred migration tool (Alembic,
Flyway, raw psycopg, manual psql, etc.) — ``drive_workspace`` doesn't
own the host's migration tooling and won't run the SQL itself.

Usage:

    from drive_workspace.migrations import principal_columns_alter_sql

    sql = principal_columns_alter_sql(
        table="users",
        principal_id_col="user_id",
        dialect="postgresql",
    )
    # SQL emitted ready to run via host's migration system
    db.execute(sql)

The function is intentionally side-effect-free; it does not connect to a
database or import any DB driver. Hosts that want a richer surface
(multi-table, downgrade, snapshot, etc.) should write their own migration
using ``drive_workspace_principals`` (the default impl's table) as a
reference.

This module is for hosts wrapping their *existing* user table; hosts using
``SqlAlchemyPrincipalStore`` directly do not need it (use that store's
``create_all`` helper).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

Dialect = Literal["postgresql", "mysql", "sqlite"]
Quoter = Callable[[str], str]


def principal_columns_alter_sql(
    *,
    table: str,
    principal_id_col: str = "id",  # reserved for future reverse-FK use; ignored
    dialect: Dialect = "postgresql",
    folder_col: str = "drive_folder_id",
    spreadsheet_col: str = "drive_spreadsheet_id",
    revoked_col: str = "drive_revoked_at",
) -> str:
    """Return ``ALTER TABLE`` SQL adding the drive_workspace columns.

    Args:
        table: Host's existing user/principal table name.
        principal_id_col: Reserved for future use (see Notes). Pass the
            host's PK column name; ignored in this version.
        dialect: SQL dialect; affects identifier quoting and timestamp type.
        folder_col: Column name for the per-principal Drive folder id.
        spreadsheet_col: Column name for the per-principal log Sheet id.
        revoked_col: Column name for the per-principal revocation
            timestamp; ``NULL`` for active principals.

    Returns:
        A multi-statement SQL string. The host's migration tool runs it
        as one or more statements depending on its splitting rules.
        The string is safe to print; it contains no secrets.

    Raises:
        ValueError: if ``dialect`` is not in ``Literal["postgresql", "mysql",
            "sqlite"]`` — ``Literal`` enforces this at static-check time, but
            the runtime check defends against ``cast``-using callers.

    Notes:
        - All three columns are added as nullable. Active principals have
          non-null ``folder_col`` and ``spreadsheet_col``; revoked
          principals have non-null ``revoked_col``.
        - ``principal_id_col`` is currently unused but accepted so the
          signature can grow a reverse-FK option later (``ALTER TABLE
          drive_workspace_audit ADD CONSTRAINT ... REFERENCES ...``)
          without a breaking change.
        - The host MUST run this in a transaction with its own backups in
          place. ``drive_workspace`` does not warn or guard.
        - See ``backend/drive_workspace/stores/sqlalchemy.py`` for the
          equivalent column shapes the default impl uses.
    """
    if dialect not in ("postgresql", "mysql", "sqlite"):
        raise ValueError(f"Unsupported dialect: {dialect!r}")

    quote = _identifier_quote(dialect)
    timestamp_type = "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "TIMESTAMP"

    return _DDL_TEMPLATE.format(
        q_table=quote(table),
        q_folder=quote(folder_col),
        q_sheet=quote(spreadsheet_col),
        q_revoked=quote(revoked_col),
        timestamp_type=timestamp_type,
    )


_DDL_TEMPLATE = """\
ALTER TABLE {q_table} ADD COLUMN {q_folder} VARCHAR(255) NULL;
ALTER TABLE {q_table} ADD COLUMN {q_sheet} VARCHAR(255) NULL;
ALTER TABLE {q_table} ADD COLUMN {q_revoked} {timestamp_type} NULL;
"""


def _identifier_quote(dialect: Dialect) -> Quoter:
    if dialect in ("postgresql", "sqlite"):
        return _double_quote
    if dialect == "mysql":
        return _backtick_quote
    raise ValueError(f"Unsupported dialect: {dialect!r}")


def _double_quote(name: str) -> str:
    if '"' in name:
        raise ValueError(f"Identifier contains forbidden character: {name!r}")
    return f'"{name}"'


def _backtick_quote(name: str) -> str:
    if "`" in name:
        raise ValueError(f"Identifier contains forbidden character: {name!r}")
    return f"`{name}`"
