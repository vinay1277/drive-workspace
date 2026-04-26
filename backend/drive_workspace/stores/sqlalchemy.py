"""Default SQLAlchemy 2.x-backed PrincipalStore.

Per ADR-0004, this is the default impl that ships with the package; hosts
on a non-SQL persistence layer write their own against
`drive_workspace.stores.protocol.PrincipalStore`.

Per ADR-0006, sync SQLAlchemy 2.x. No Alembic yet — the schema is still
moving; ship a `create_all` helper for tests and demos and revisit in
Phase 3 once the schema is stable.

The `Principal` model is an implementation detail of this default impl;
the `PrincipalStore` Protocol stays opaque (string-keyed input, narrow
return shapes). Hosts that wrap their own user table do not see this
model at all.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Engine, String
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for the default store's tables.

    Hosts using this default impl can `create_all(engine)` against this base
    to provision the schema. Hosts using their own `PrincipalStore` impl do
    not need to import this.
    """


class Principal(Base):
    __tablename__ = "drive_workspace_principals"

    principal_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    folder_id: Mapped[str] = mapped_column(String(255), nullable=False)
    spreadsheet_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    granted_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provisioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def create_all(engine: Engine) -> None:
    """Create the default-impl tables. Test/demo helper; not for production."""
    Base.metadata.create_all(engine)


class SqlAlchemyPrincipalStore:
    """Default `PrincipalStore` impl backed by a SQLAlchemy 2.x session factory.

    The host owns the engine and the `sessionmaker`; the store opens its own
    short-lived session per call so the package's persistence concern stays
    self-contained within a request. Hosts that need a different unit-of-work
    boundary write their own `PrincipalStore`.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_folder_id(self, principal_id: str) -> str | None:
        with self._session_factory() as session:
            row = session.get(Principal, principal_id)
            if row is None or row.revoked_at is not None:
                return None
            return row.folder_id

    def get_spreadsheet_id(self, principal_id: str) -> str | None:
        with self._session_factory() as session:
            row = session.get(Principal, principal_id)
            if row is None or row.revoked_at is not None:
                return None
            return row.spreadsheet_id

    def record_provisioned(
        self,
        principal_id: str,
        folder_id: str,
        spreadsheet_id: str,
    ) -> None:
        """Insert or update a principal row.

        Idempotent: re-provisioning an existing principal refreshes the
        folder + spreadsheet ids and clears `revoked_at`. This matches the
        FolderManager.provision() lifecycle — a re-onboard after offboarding
        should resurrect the same principal_id.
        """
        now = datetime.now(UTC)
        with self._session_factory.begin() as session:
            existing = session.get(Principal, principal_id)
            if existing is None:
                session.add(
                    Principal(
                        principal_id=principal_id,
                        folder_id=folder_id,
                        spreadsheet_id=spreadsheet_id,
                        provisioned_at=now,
                    )
                )
            else:
                existing.folder_id = folder_id
                existing.spreadsheet_id = spreadsheet_id
                existing.provisioned_at = now
                existing.revoked_at = None

    def record_revoked(self, principal_id: str) -> None:
        """Mark a principal as revoked. No-op if the row does not exist."""
        with self._session_factory.begin() as session:
            existing = session.get(Principal, principal_id)
            if existing is None:
                return
            existing.revoked_at = datetime.now(UTC)
