"""Unit tests for the LogSchema Protocol via the ExampleLogSchema fixture."""

from __future__ import annotations

from drive_workspace.logs import ColumnSpec, LogSchema
from drive_workspace.tests._fixtures.example_log_schema import ExampleLogSchema


def test_columns_returns_columnspecs() -> None:
    schema = ExampleLogSchema()
    cols = schema.columns()
    assert len(cols) == 4
    assert all(isinstance(c, ColumnSpec) for c in cols)
    assert [c.key for c in cols] == [
        "timestamp",
        "principal_id",
        "note",
        "photo_link",
    ]


def test_render_row_length_matches_columns() -> None:
    schema = ExampleLogSchema()
    row = schema.render_row(
        {
            "timestamp": "2026-04-27T12:00:00Z",
            "principal_id": "alice",
            "note": "submitted",
            "photo_link": "https://drive.google.com/file/d/abc",
        }
    )
    assert len(row) == len(schema.columns())


def test_render_row_aligns_with_column_order() -> None:
    schema = ExampleLogSchema()
    row = schema.render_row(
        {
            "timestamp": "2026-04-27T12:00:00Z",
            "principal_id": "alice",
            "note": "submitted",
            "photo_link": "https://drive.google.com/file/d/abc",
        }
    )
    assert row == [
        "2026-04-27T12:00:00Z",
        "alice",
        "submitted",
        "https://drive.google.com/file/d/abc",
    ]


def test_render_row_missing_keys_become_none() -> None:
    schema = ExampleLogSchema()
    row = schema.render_row({"principal_id": "alice"})
    assert row == [None, "alice", None, None]


def test_columns_returns_fresh_list() -> None:
    """Mutating the returned list must not affect subsequent calls."""
    schema = ExampleLogSchema()
    cols = schema.columns()
    cols.clear()
    assert len(schema.columns()) == 4


def test_protocol_compatibility() -> None:
    schema: LogSchema = ExampleLogSchema()
    assert schema.columns()
    assert schema.render_row({}) == [None, None, None, None]
