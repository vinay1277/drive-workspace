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


# ── Phase 3.5: second LogSchema impl validates the abstraction ────────────


def test_inspection_schema_protocol_compatibility() -> None:
    from drive_workspace.tests._fixtures.inspection_log_schema import (
        InspectionLogSchema,
    )

    schema: LogSchema = InspectionLogSchema()
    cols = schema.columns()
    assert len(cols) == 7
    assert all(isinstance(c, ColumnSpec) for c in cols)


def test_inspection_schema_render_aligns_with_columns() -> None:
    from drive_workspace.tests._fixtures.inspection_log_schema import (
        InspectionLogSchema,
    )

    schema = InspectionLogSchema()
    row = schema.render_row(
        {
            "inspection_id": "INSP-42",
            "inspector_email": "alice@org.com",
            "location_lat": 26.7,
            "location_lng": 85.3,
            "score": 92,
            "photo_id": "1abc",
            "notes": "Nominal",
        }
    )
    assert len(row) == len(schema.columns())
    # inspected_at is server-rendered formula, not from payload
    assert row[0] == "=NOW()"
    assert row[1] == "INSP-42"
    assert row[2] == "alice@org.com"
    assert row[3] == "26.7, 85.3"
    assert row[4] == "OK"  # score 92 >= 80
    assert row[5] == '=HYPERLINK("https://drive.google.com/file/d/1abc/view","photo")'
    assert row[6] == "Nominal"


def test_inspection_schema_status_below_threshold() -> None:
    from drive_workspace.tests._fixtures.inspection_log_schema import (
        InspectionLogSchema,
    )

    schema = InspectionLogSchema()
    row = schema.render_row({"score": 79})
    # status column is index 4
    assert row[4] == "REVIEW"


def test_inspection_schema_handles_missing_keys() -> None:
    from drive_workspace.tests._fixtures.inspection_log_schema import (
        InspectionLogSchema,
    )

    schema = InspectionLogSchema()
    row = schema.render_row({})
    # Length still matches; composed/derived/formula cells degrade to None
    # except inspected_at which is always =NOW().
    assert len(row) == 7
    assert row[0] == "=NOW()"
    assert row[3] is None  # location: needs both lat and lng
    assert row[4] is None  # status: needs score
    assert row[5] is None  # photo: needs photo_id


def test_inspection_schema_hyperlink_label_quote_escape() -> None:
    """A label containing `"` must be escaped to prevent formula injection."""
    from drive_workspace.tests._fixtures.inspection_log_schema import (
        InspectionLogSchema,
    )

    cell = InspectionLogSchema._hyperlink("xyz", 'evil"label')
    # `"` doubled to `""` per Sheets formula-string-literal escaping
    assert cell == '=HYPERLINK("https://drive.google.com/file/d/xyz/view","evil""label")'
