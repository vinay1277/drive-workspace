"""drive_workspace — backend-mediated Google Drive uploads.

Phase 1: package is importable but does no real work yet. Public surface
mirrors the architecture sketch; methods raise NotImplementedError.
"""

from drive_workspace.folders import FolderManager
from drive_workspace.logs import SpreadsheetLogger
from drive_workspace.reconcile import ReconciliationRunner
from drive_workspace.uploads import FileSpec, UploadSession, UploadSessionMint
from drive_workspace.workspace import Authenticator, DriveWorkspace

__all__ = [
    "Authenticator",
    "DriveWorkspace",
    "FileSpec",
    "FolderManager",
    "ReconciliationRunner",
    "SpreadsheetLogger",
    "UploadSession",
    "UploadSessionMint",
]

__version__ = "0.0.1"
