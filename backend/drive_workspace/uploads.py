"""UploadSessionMint — resumable upload session minting. Phase 1 stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace


@dataclass(frozen=True)
class FileSpec:
    file_name: str
    mime_type: str
    file_size_bytes: int
    kind: str  # "photo" | "audio" | "video"


@dataclass(frozen=True)
class UploadSession:
    upload_url: str
    drive_file_id: str
    expires_at: str  # ISO-8601


class UploadSessionMint:
    def __init__(self, dw: DriveWorkspace) -> None:
        self._dw = dw

    def initiate(
        self,
        principal_id: str,
        files: list[FileSpec],
    ) -> list[UploadSession]:
        raise NotImplementedError("Phase 2")
