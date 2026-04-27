"""drive_workspace — backend-mediated Google Drive uploads.

Phase 1: package is importable but does no real work yet. Public surface
mirrors the architecture sketch; methods raise NotImplementedError.
"""

from drive_workspace.auth import FileAuthenticator
from drive_workspace.folders import FolderManager
from drive_workspace.logs import ColumnSpec, LogSchema, SpreadsheetLogger
from drive_workspace.migrations import principal_columns_alter_sql
from drive_workspace.reconcile import ReconciliationRunner
from drive_workspace.uploads import FileSpec, UploadSession, UploadSessionMint
from drive_workspace.workspace import Authenticator, DriveWorkspace

#: Hard cap on a single ``initiate-upload`` prefetch batch. Mirrors
#: ``DriveUploader.MAX_PREFETCH_COUNT`` on the Android library side
#: (see ADR-0003). Canonical home for both the package's Flask
#: adapter and the reference server. Keeps an accidental
#: ``?count=1000000`` from minting an unbounded batch.
MAX_PREFETCH_COUNT: int = 50

__all__ = [
    "MAX_PREFETCH_COUNT",
    "Authenticator",
    "ColumnSpec",
    "DriveWorkspace",
    "FileAuthenticator",
    "FileSpec",
    "FolderManager",
    "LogSchema",
    "ReconciliationRunner",
    "SpreadsheetLogger",
    "UploadSession",
    "UploadSessionMint",
    "principal_columns_alter_sql",
]

__version__ = "0.0.1"
