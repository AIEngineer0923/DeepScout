"""Short-lived dependency probes that do not leak engines or Redis clients."""

from __future__ import annotations

from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

REQUIRED_ALEMBIC_REVISION = "013"


def probe_postgres(database_url: str) -> str:
    engine = create_engine(database_url, pool_pre_ping=True, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "unavailable"
    finally:
        engine.dispose()


def probe_postgres_schema(database_url: str) -> str:
    """Verify required Alembic revision and evaluation persistence table."""
    engine = create_engine(database_url, pool_pre_ping=True, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            if revision != REQUIRED_ALEMBIC_REVISION:
                return f"schema_outdated:{revision}"
            has_table = conn.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = current_schema() AND table_name = 'evaluation_results'"
                    ")"
                )
            ).scalar_one()
            if not has_table:
                return "missing_evaluation_results"
        return "ok"
    except Exception:
        return "unavailable"
    finally:
        engine.dispose()


def probe_redis(redis_url: str) -> str:
    client = Redis.from_url(redis_url, socket_connect_timeout=2)
    try:
        client.ping()
        return "ok"
    except Exception:
        return "unavailable"
    finally:
        client.close()
