import pytest
from alembic import command
from deepscout_persistence.migrations import alembic_config
from deepscout_persistence.session import get_engine
from sqlalchemy import text
from tests.db_helpers import database_url, postgres_available


@pytest.mark.postgres
def test_migrations_apply_from_blank_database() -> None:
    if not postgres_available():
        pytest.skip("PostgreSQL is not available for migration tests")

    config = alembic_config()

    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = get_engine(database_url())
    with engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass('public.research_runs')")).scalar() is not None
        vector_installed = conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        ).scalar()
        assert vector_installed is True

    command.downgrade(config, "base")
    command.upgrade(config, "head")
