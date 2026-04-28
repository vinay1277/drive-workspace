"""UploadSessionMint — resumable upload session minting.

Phase 2B: real implementation against Drive's resumable upload API.

Per session, two Drive calls are made:

  1. ``files.create`` (multipart, empty body) — pre-creates the file
     metadata under the principal's folder. Returns the
     ``drive_file_id`` upfront so the host can echo it back to the
     client at initiate time (the Android library treats this id as
     stable from initiate through completion).
  2. ``files.update`` with ``uploadType=resumable`` — mints the
     session URL the client will PUT chunks to.

This is two API calls instead of the canonical one-call resumable
flow because Drive's create+upload-in-one only returns the file id on
the upload's last chunk — too late for the synchronous initiate
contract. The cost is one extra round-trip per FileSpec at session
mint time; the tradeoff is paid once and gives the V2 client a stable
``remoteFileId`` from the first event.

Per ADR-0011, every Drive call passes ``supportsAllDrives=True`` so
operations target the Shared Drive named by
``DriveWorkspace.shared_drive_id``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace

logger = logging.getLogger(__name__)

# Drive's documented resumable-session TTL is 7 days. The prefetch bank
# (Android side) prunes at 5 days for a 2-day safety margin; this
# value is informational only — Drive enforces the real expiry.
_RESUMABLE_SESSION_TTL_DAYS = 7


@dataclass(frozen=True)
class FileSpec:
    """Description of one file the host wants to upload.

    Attributes:
        file_name: Display name on Drive.
        mime_type: Drive uses this as the resumable session's
            ``Content-Type``. ``application/octet-stream`` is
            acceptable when the real type is unknown.
        file_size_bytes: Total file size in bytes; used as an
            initial size hint and the prefetch-fingerprint axis.
        kind: Coarse host-defined bucket (``"photo"``, ``"audio"``,
            ``"video"``); a prefetch-fingerprint axis on the device.
    """

    file_name: str
    mime_type: str
    file_size_bytes: int
    kind: str


@dataclass(frozen=True)
class UploadSession:
    """Resumable upload session returned by ``UploadSessionMint.initiate``.

    Attributes:
        upload_url: Resumable PUT endpoint; the device chunks bytes
            against this URL directly. Single-use, single-file.
        drive_file_id: Drive file id; stable from initiate through
            completion (V2 echoes it back to the host on
            ``UploadProgress.Succeeded``).
        expires_at: ISO-8601 timestamp string. Drive's documented
            TTL is 7 days; the prefetch bank prunes at 5 days for
            a 2-day safety margin.
    """

    upload_url: str
    drive_file_id: str
    expires_at: str


class UploadSessionMint:
    """Mint resumable Drive upload sessions for a principal.

    Exposed as ``DriveWorkspace.uploads``. Hosts do not construct this
    class directly; the optional ``drive_workspace.adapters.flask``
    blueprint wraps it in the ``POST /api/drive/initiate-upload``
    endpoint.
    """

    def __init__(self, dw: DriveWorkspace) -> None:
        self._dw = dw

    def initiate(
        self,
        principal_id: str,
        files: list[FileSpec],
    ) -> list[UploadSession]:
        """Mint one resumable session per ``FileSpec`` in ``files``.

        Lazy-provisions the principal if no folder mapping exists yet
        (display_name defaults to ``principal_id``; no email share
        because no email is known at upload time).

        Args:
            principal_id: Stable identifier.
            files: One or more file specs; every spec gets one
                session. Pass the same spec N times for a prefetch
                batch.

        Returns:
            A list of ``UploadSession`` rows aligned with ``files``.
        """
        if not files:
            return []

        folder_id = self._dw.principals.provision_lazy(principal_id)
        creds = self._dw.auth.credential()
        sessions: list[UploadSession] = []

        for spec in files:
            file_id = self._create_placeholder_file(
                creds=creds, folder_id=folder_id, spec=spec,
            )
            upload_url = self._start_resumable_session(
                creds=creds, file_id=file_id, spec=spec,
            )
            sessions.append(
                UploadSession(
                    upload_url=upload_url,
                    drive_file_id=file_id,
                    expires_at=_iso_expires_in_days(_RESUMABLE_SESSION_TTL_DAYS),
                )
            )

        logger.info(
            "drive_workspace.initiate: principal=%s minted=%d folder=%s",
            principal_id, len(sessions), folder_id,
        )
        return sessions

    # ------------------------------------------------------------------
    # DRIVE API HELPERS
    # ------------------------------------------------------------------

    def _create_placeholder_file(
        self,
        *,
        creds: Any,
        folder_id: str,
        spec: FileSpec,
    ) -> str:
        """Pre-create the file metadata; return the new file id.

        The file is created with no content (empty body). The
        subsequent ``files.update`` with ``uploadType=resumable``
        attaches bytes via the resumable session URL.
        """
        from googleapiclient.discovery import build

        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        created = drive.files().create(
            body={
                "name": spec.file_name,
                "parents": [folder_id],
                "mimeType": spec.mime_type,
            },
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return str(created["id"])

    def _start_resumable_session(
        self,
        *,
        creds: Any,
        file_id: str,
        spec: FileSpec,
    ) -> str:
        """PATCH the file with ``uploadType=resumable``; return upload URL.

        The Drive resumable upload endpoint responds to the initiation
        POST/PATCH with the session URL in the ``Location`` header.
        We use ``google.auth.transport.requests.AuthorizedSession`` so
        the SA bearer token is attached automatically and refreshed on
        the boundary.
        """
        from google.auth.transport.requests import AuthorizedSession

        url = (
            f"https://www.googleapis.com/upload/drive/v3/files/{file_id}"
            f"?uploadType=resumable&supportsAllDrives=true"
        )
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": spec.mime_type,
        }
        if spec.file_size_bytes > 0:
            headers["X-Upload-Content-Length"] = str(spec.file_size_bytes)

        # Empty JSON body — we're only updating bytes, not metadata.
        session = AuthorizedSession(creds)
        response = session.patch(url, headers=headers, data=json.dumps({}))

        if response.status_code != 200:
            raise RuntimeError(
                f"Drive resumable session init failed: HTTP {response.status_code} "
                f"body={response.text!r}"
            )

        location = response.headers.get("Location")
        if not location:
            raise RuntimeError(
                "Drive resumable session init succeeded but Location header is missing"
            )
        return str(location)


def _iso_expires_in_days(days: int) -> str:
    """Return an ISO-8601 UTC timestamp ``days`` from now."""
    expiry = datetime.now(tz=UTC) + timedelta(days=days)
    return expiry.strftime("%Y-%m-%dT%H:%M:%SZ")
