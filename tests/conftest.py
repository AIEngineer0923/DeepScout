"""Shared PostgreSQL test fixtures."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from alembic import command
from deepscout_persistence.migrations import alembic_config
from deepscout_persistence.session import get_engine
from deepscout_persistence.store import ResearchStore
from sqlalchemy.orm import Session
from tests.db_helpers import database_url, postgres_available


@pytest.fixture(scope="session")
def postgres_ready() -> None:
    if not postgres_available():
        pytest.skip("PostgreSQL is not available for persistence tests")
    config = alembic_config()
    os.environ["DATABASE_URL"] = database_url()
    command.upgrade(config, "head")


@pytest.fixture
def db_session(postgres_ready: None) -> Generator[Session, None, None]:
    engine = get_engine(database_url())
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def store(db_session: Session) -> ResearchStore:
    return ResearchStore(db_session)


@pytest.fixture
def settings():
    from deepscout_core.settings import Settings
    from deepscout_core.types import ProviderKind

    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE, RESEARCH_WORKERS_INLINE=True)
