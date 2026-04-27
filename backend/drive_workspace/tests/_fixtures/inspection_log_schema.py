"""Second `LogSchema` reference implementation, intentionally different shape.

Phase 3.5 (maturity checklist) requires two distinct ``LogSchema``
implementations to validate that the abstraction holds. ``ExampleLogSchema``
covers the minimal symmetric case (4 columns, 1:1 with payload keys);
``InspectionLogSchema`` here covers the asymmetric case:

- More columns than payload keys (a column derived from multiple keys)
- A ``=HYPERLINK(...)`` formula cell with quote-escaping
- A computed cell (status badge derived from a numeric score)
- A column that intentionally does NOT come from a payload key
  (rendered server-side at append time as ``=NOW()`` formula)

If the Protocol survives these two shapes, hosts adapting to other
domains (medical inspections, fleet logs, time-tracking, etc.) should
fit without package changes.
"""

from __future__ import annotations

from typing import Any, TypedDict

from drive_workspace.logs import ColumnSpec


class InspectionLogPayload(TypedDict, total=False):
    """Payload shape InspectionLogSchema accepts.

    Asymmetric to the column list — one column composes from two keys
    (``location_lat`` + ``location_lng`` → ``location``); one is
    derived (``score`` → ``status_badge``); one is server-rendered
    (``inspected_at`` not in payload, comes from ``=NOW()``).
    """

    inspection_id: str
    inspector_email: str
    location_lat: float
    location_lng: float
    score: int
    photo_id: str
    notes: str


class InspectionLogSchema:
    """Asymmetric inspection log: 7 columns, 6 payload keys.

    Columns and rendering rules:

    1. ``inspected_at`` — formula ``=NOW()``, no payload key
    2. ``inspection_id`` — straight passthrough
    3. ``inspector`` — straight from ``inspector_email``
    4. ``location`` — composed: ``"<lat>, <lng>"`` from two payload keys
    5. ``status`` — derived: ``OK`` if score ≥ 80, else ``REVIEW``
    6. ``photo`` — ``=HYPERLINK(...)`` formula, with `"` in label escaped
    7. ``notes`` — straight passthrough
    """

    _COLUMNS: tuple[ColumnSpec, ...] = (
        ColumnSpec(key="inspected_at", header="Inspected At"),
        ColumnSpec(key="inspection_id", header="Inspection ID"),
        ColumnSpec(key="inspector", header="Inspector"),
        ColumnSpec(key="location", header="Location"),
        ColumnSpec(key="status", header="Status"),
        ColumnSpec(key="photo", header="Photo"),
        ColumnSpec(key="notes", header="Notes"),
    )

    _PASS_THRESHOLD = 80
    _DRIVE_FILE_URL = "https://drive.google.com/file/d/{}/view"

    def columns(self) -> list[ColumnSpec]:
        return list(self._COLUMNS)

    def render_row(self, payload: dict[str, Any]) -> list[Any]:
        lat = payload.get("location_lat")
        lng = payload.get("location_lng")
        location = f"{lat}, {lng}" if lat is not None and lng is not None else None

        score = payload.get("score")
        status: str | None
        if score is None:
            status = None
        elif score >= self._PASS_THRESHOLD:
            status = "OK"
        else:
            status = "REVIEW"

        photo_id = payload.get("photo_id")
        photo_cell = self._hyperlink(photo_id, "photo") if photo_id else None

        return [
            "=NOW()",                          # inspected_at — server-rendered
            payload.get("inspection_id"),      # passthrough
            payload.get("inspector_email"),    # passthrough (renamed column)
            location,                           # composed
            status,                             # derived
            photo_cell,                         # formula
            payload.get("notes"),              # passthrough
        ]

    @classmethod
    def _hyperlink(cls, file_id: str, label: str) -> str:
        # Escape inner quotes in label to prevent formula injection.
        safe_label = label.replace('"', '""')
        url = cls._DRIVE_FILE_URL.format(file_id)
        return f'=HYPERLINK("{url}","{safe_label}")'
