"""ReconciliationRunner — orphan detection and cleanup.

Phase 1 stub. Phase 2B implements the algorithm: list resumable
sessions the backend believes are still in flight, ask Drive
whether each one resolved or expired, prune the orphans. Exposed
as ``python -m drive_workspace.reconcile`` per the Phase 2 plan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drive_workspace.workspace import DriveWorkspace


class ReconciliationRunner:
    """Detect and clean up orphaned upload sessions.

    A session is orphaned when the backend minted it but the device
    never completed the upload (network drop, app reinstall, etc.).
    These sessions count against Drive's per-folder concurrent-resumable
    limit until their 7-day TTL expires; the runner cleans them up
    proactively.

    Exposed as ``DriveWorkspace.reconcile``. Phase 2B also wires a
    ``python -m drive_workspace.reconcile`` CLI for cron use.
    """

    def __init__(self, dw: DriveWorkspace) -> None:
        self._dw = dw

    def run(self) -> None:
        """Run one reconciliation pass.

        Walks the host's record of in-flight sessions, queries each
        against Drive (was the file actually created?), drops or
        marks-as-orphaned per the result. Idempotent and safe to
        run on a schedule.

        Raises:
            NotImplementedError: Phase 1 stub.
        """
        raise NotImplementedError("Phase 2")
