"""Tests for SqlAlchemyPrincipalStore.

Two test classes:

- `TestSqlAlchemyPrincipalStoreSqlite` runs against `sqlite:///:memory:`.
  Always-on; this is the unit coverage.
- `TestSqlAlchemyPrincipalStorePostgres` runs against a real Postgres reached
  via the `DRIVE_WS_POSTGRES_URL` env var. Skipped by default so the suite
  doesn't require Docker. Use `docker compose up -d postgres` and set the
  env var to enable.

Env-var gating (rather than a pytest marker) was chosen so the default
`pytest` invocation requires no extra flags and no Docker on the dev box.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from drive_workspace.stores.protocol import PrincipalStore
from drive_workspace.stores.sqlalchemy import (
    Base,
    Principal,
    SqlAlchemyPrincipalStore,
    create_all,
)


def _store_contract(store: SqlAlchemyPrincipalStore) -> None:
    """Exercises the PrincipalStore Protocol surface. Reused per backend."""
    # Empty state
    assert store.get_folder_id("alice") is None
    assert store.get_spreadsheet_id("alice") is None

    # Provision
    store.record_provisioned("alice", "folder-A1", "sheet-A1")
    assert store.get_folder_id("alice") == "folder-A1"
    assert store.get_spreadsheet_id("alice") == "sheet-A1"

    # Idempotent re-provision: ids refresh, revoked_at clears
    store.record_provisioned("alice", "folder-A2", "sheet-A2")
    assert store.get_folder_id("alice") == "folder-A2"
    assert store.get_spreadsheet_id("alice") == "sheet-A2"

    # Revoke: queries return None
    store.record_revoked("alice")
    assert store.get_folder_id("alice") is None
    assert store.get_spreadsheet_id("alice") is None

    # Re-provision after revoke resurrects
    store.record_provisioned("alice", "folder-A3", "sheet-A3")
    assert store.get_folder_id("alice") == "folder-A3"

    # Revoking an unknown principal is a no-op (does not raise)
    store.record_revoked("never-existed")

    # Multiple principals do not collide
    store.record_provisioned("bob", "folder-B1", "sheet-B1")
    assert store.get_folder_id("bob") == "folder-B1"
    assert store.get_folder_id("alice") == "folder-A3"


class TestSqlAlchemyPrincipalStoreSqlite:
    @pytest.fixture
    def engine(self) -> Engine:
        return create_engine("sqlite:///:memory:")

    @pytest.fixture
    def session_factory(self, engine: Engine) -> sessionmaker[Session]:
        create_all(engine)
        return sessionmaker(bind=engine, expire_on_commit=False)

    def test_protocol_compatibility(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        """SqlAlchemyPrincipalStore satisfies the structural PrincipalStore Protocol."""
        store: PrincipalStore = SqlAlchemyPrincipalStore(session_factory)
        assert store.get_folder_id("nobody") is None

    def test_full_lifecycle(self, session_factory: sessionmaker[Session]) -> None:
        store = SqlAlchemyPrincipalStore(session_factory)
        _store_contract(store)

    def test_provisioned_at_is_set(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        store = SqlAlchemyPrincipalStore(session_factory)
        store.record_provisioned("alice", "f1", "s1")
        with session_factory() as s:
            row = s.get(Principal, "alice")
            assert row is not None
            assert row.provisioned_at is not None
            assert row.revoked_at is None

    def test_revoked_at_is_set_on_revoke(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        store = SqlAlchemyPrincipalStore(session_factory)
        store.record_provisioned("alice", "f1", "s1")
        store.record_revoked("alice")
        with session_factory() as s:
            row = s.get(Principal, "alice")
            assert row is not None
            assert row.revoked_at is not None

    def test_create_all_is_idempotent(self, engine: Engine) -> None:
        create_all(engine)
        create_all(engine)  # second call must not raise


_POSTGRES_URL = os.environ.get("DRIVE_WS_POSTGRES_URL")


@pytest.mark.skipif(
    _POSTGRES_URL is None,
    reason="Set DRIVE_WS_POSTGRES_URL to run postgres-backed store tests.",
)
class TestSqlAlchemyPrincipalStorePostgres:
    @pytest.fixture
    def engine(self) -> Iterator[Engine]:
        assert _POSTGRES_URL is not None
        eng = create_engine(_POSTGRES_URL)
        # Clean slate on the public schema's drive_workspace_principals table.
        with eng.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS drive_workspace_principals"))
        Base.metadata.create_all(eng)
        try:
            yield eng
        finally:
            with eng.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS drive_workspace_principals"))
            eng.dispose()

    @pytest.fixture
    def session_factory(self, engine: Engine) -> sessionmaker[Session]:
        return sessionmaker(bind=engine, expire_on_commit=False)

    def test_full_lifecycle(self, session_factory: sessionmaker[Session]) -> None:
        store = SqlAlchemyPrincipalStore(session_factory)
        _store_contract(store)
