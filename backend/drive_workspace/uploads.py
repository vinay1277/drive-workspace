"""UploadSessionMint — resumable upload session minting.

Phase 1 stub. Phase 2B replaces ``initiate``'s body with real
Drive ``files.create`` + ``uploadType=resumable`` calls; the wire
shape (one or N ``UploadSession`` rows per request) stays the same
to honour the prefetch-bank contract from ADR-0003.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace


@dataclass(frozen=True)
class FileSpec:
    """Description of one file the host wants to upload.

    Passed by the host to ``UploadSessionMint.initiate``;
    ``UploadSessionMint`` returns one ``UploadSession`` per
    ``FileSpec`` in the same order. For prefetch (count > 1) the
    same ``FileSpec`` is typically passed N times as a template —
    the bank fingerprints by ``mime_type`` + ``kind`` + size bracket
    on the Android side, so a 1-byte placeholder ``file_size_bytes``
    is fine when the real size isn't known yet.

    Attributes:
        file_name: Display name on Drive. Not used by the upload
            engine for anything but visibility in the Drive UI.
        mime_type: Drive uses this as the resumable session's
            ``Content-Type``. Must be set; ``application/octet-stream``
            is acceptable when the real type is unknown.
        file_size_bytes: Total file size in bytes. Drive trusts the
            chunked-PUT ``Content-Range`` headers at upload time;
            this value is the initial size hint and is also what the
            prefetch bank uses to pick the size bracket.
        kind: Coarse host-defined bucket — typically ``"photo"``,
            ``"audio"``, or ``"video"``. Used as a prefetch-fingerprint
            axis on the device.
    """

    file_name: str
    mime_type: str
    file_size_bytes: int
    kind: str


@dataclass(frozen=True)
class UploadSession:
    """Resumable upload session returned by ``UploadSessionMint.initiate``.

    The Android library treats ``upload_url`` as opaque. ``expires_at``
    is informational; if the URL has actually expired the engine
    detects it via the 410/404 response and re-initiates.

    Attributes:
        upload_url: Resumable PUT endpoint; the device chunks bytes
            against this URL directly. Single-use, single-file.
        drive_file_id: Drive file id; echoed back to the host on
            ``UploadProgress.Succeeded``.
        expires_at: ISO-8601 timestamp string. Drive's documented
            TTL is 7 days; the prefetch bank prunes at 5 days for a
            2-day safety margin.
    """

    upload_url: str
    drive_file_id: str
    expires_at: str


class UploadSessionMint:
    """Mint resumable Drive upload sessions for a principal.

    Exposed as ``DriveWorkspace.uploads``. Hosts do not construct
    this class directly; the optional ``drive_workspace.adapters.flask``
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

        Phase 2B will resolve the principal's folder via
        ``DriveWorkspace.principal_store.get_folder_id``, set
        ``parents=[folder_id]`` and ``supportsAllDrives=True`` on
        every Drive call (per ADR-0011), and return the array of
        sessions in input order. The Android library passes
        ``count=1`` for synchronous upload and ``count=N`` for
        prefetch (ADR-0003); the Flask adapter forwards the count.

        Args:
            principal_id: Stable identifier (must already be
                provisioned via ``FolderManager.provision``).
            files: One or more file specs; every spec gets one
                session. Pass the same spec N times for a prefetch
                batch.

        Returns:
            A list of ``UploadSession`` rows aligned with ``files``.

        Raises:
            NotImplementedError: Phase 1 stub.
        """
        raise NotImplementedError("Phase 2")
