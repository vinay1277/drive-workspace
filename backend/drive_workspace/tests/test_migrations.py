"""Tests for drive_workspace.migrations.principal_columns_alter_sql."""

from __future__ import annotations

import pytest

from drive_workspace.migrations import principal_columns_alter_sql


def test_postgresql_default_columns() -> None:
    sql = principal_columns_alter_sql(table="users")
    assert 'ALTER TABLE "users" ADD COLUMN "drive_folder_id" VARCHAR(255) NULL;' in sql
    assert (
        'ALTER TABLE "users" ADD COLUMN "drive_spreadsheet_id" VARCHAR(255) NULL;'
        in sql
    )
    assert (
        'ALTER TABLE "users" ADD COLUMN "drive_revoked_at" '
        "TIMESTAMP WITH TIME ZONE NULL;" in sql
    )


def test_mysql_uses_backticks_and_plain_timestamp() -> None:
    sql = principal_columns_alter_sql(table="surveyors", dialect="mysql")
    assert "ALTER TABLE `surveyors` ADD COLUMN `drive_folder_id` VARCHAR(255) NULL;" in sql
    assert "TIMESTAMP NULL;" in sql
    assert "TIMESTAMP WITH TIME ZONE" not in sql


def test_sqlite_uses_double_quotes_and_plain_timestamp() -> None:
    sql = principal_columns_alter_sql(table="users", dialect="sqlite")
    assert 'ALTER TABLE "users"' in sql
    assert "TIMESTAMP NULL;" in sql
    assert "TIMESTAMP WITH TIME ZONE" not in sql


def test_custom_column_names() -> None:
    sql = principal_columns_alter_sql(
        table="my_table",
        folder_col="dw_folder",
        spreadsheet_col="dw_sheet",
        revoked_col="dw_revoked",
    )
    assert '"dw_folder"' in sql
    assert '"dw_sheet"' in sql
    assert '"dw_revoked"' in sql
    assert "drive_folder_id" not in sql


def test_invalid_dialect_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported dialect"):
        principal_columns_alter_sql(table="users", dialect="oracle")  # type: ignore[arg-type]


def test_double_quote_in_postgres_identifier_rejected() -> None:
    """Defense against ``cast``-using callers passing crafted identifiers."""
    with pytest.raises(ValueError, match="forbidden character"):
        principal_columns_alter_sql(table='users"; DROP TABLE x; --')


def test_backtick_in_mysql_identifier_rejected() -> None:
    with pytest.raises(ValueError, match="forbidden character"):
        principal_columns_alter_sql(
            table="users` DROP TABLE x; --", dialect="mysql"
        )


def test_emitted_sql_is_three_statements() -> None:
    sql = principal_columns_alter_sql(table="users")
    statements = [s.strip() for s in sql.strip().split(";") if s.strip()]
    assert len(statements) == 3
