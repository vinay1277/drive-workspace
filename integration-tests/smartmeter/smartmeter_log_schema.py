"""SmartMeterLogSchema — drive_workspace.LogSchema impl for survey
submissions.

Columns match the brief's spec: timestamp, ivrs_no, consumer_name,
photo_link, audio_link, video_link, gps_lat, gps_lng, status. Each
``_link`` cell renders as a Sheets ``=HYPERLINK(...)`` formula whose
target is the Drive file URL minted by drive_workspace's
``UploadSessionMint.initiate``.

Payload contract (the dict ``render_row`` accepts):

    {
        "timestamp":     "2026-05-03T14:33:21Z",  # ISO 8601 string
        "ivrs_no":       "JMC-IVRS-12345",
        "consumer_name": "Alice Example",
        "photo_id":      "1abc...",   # drive_file_id (HYPERLINK target)
        "audio_id":      "1def...",   # may be None
        "video_id":      "1ghi...",   # may be None
        "gps_lat":       21.123456,   # float, may be None
        "gps_lng":       79.123456,   # float, may be None
        "status":        "submitted", # "submitted" | "rejected" | ...
    }

Missing optional keys render as empty cells.
"""

from __future__ import annotations

from typing import Any

from drive_workspace.logs import ColumnSpec


class SmartMeterLogSchema:
    """``LogSchema`` Protocol impl for SmartMeter survey submissions."""

    _COLUMNS: tuple[ColumnSpec, ...] = (
        ColumnSpec(key="timestamp",     header="Timestamp"),
        ColumnSpec(key="ivrs_no",       header="IVRS No"),
        ColumnSpec(key="consumer_name", header="Consumer"),
        ColumnSpec(key="photo_link",    header="Photo"),
        ColumnSpec(key="audio_link",    header="Audio"),
        ColumnSpec(key="video_link",    header="Video"),
        ColumnSpec(key="gps_lat",       header="GPS Lat"),
        ColumnSpec(key="gps_lng",       header="GPS Lng"),
        ColumnSpec(key="status",        header="Status"),
    )

    def columns(self) -> list[ColumnSpec]:
        return list(self._COLUMNS)

    def render_row(self, payload: dict[str, Any]) -> list[Any]:
        return [
            payload.get("timestamp", ""),
            payload.get("ivrs_no", ""),
            payload.get("consumer_name", ""),
            self._hyperlink(payload.get("photo_id"), label="open"),
            self._hyperlink(payload.get("audio_id"), label="open"),
            self._hyperlink(payload.get("video_id"), label="open"),
            payload.get("gps_lat", ""),
            payload.get("gps_lng", ""),
            payload.get("status", ""),
        ]

    @staticmethod
    def _hyperlink(drive_file_id: str | None, label: str) -> str:
        """Render a Sheets HYPERLINK formula targeting the Drive file.

        Empty string when the id is missing — Sheets treats unset cells
        as blank, which is what we want for optional media slots.
        """
        if not drive_file_id:
            return ""
        url = f"https://drive.google.com/file/d/{drive_file_id}/view"
        # Escape embedded quotes defensively — drive_file_id is opaque
        # but the host might pass unexpected payloads in tests.
        safe_url = url.replace('"', '""')
        safe_label = label.replace('"', '""')
        return f'=HYPERLINK("{safe_url}", "{safe_label}")'
