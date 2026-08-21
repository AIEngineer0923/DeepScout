"""Short-lived dependency probes that do not leak engines or Redis clients."""

from __future__ import annotations

from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


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


def probe_redis(redis_url: str) -> str:
    client = Redis.from_url(redis_url, socket_connect_timeout=2)
    try:
        client.ping()
        return "ok"
    except Exception:
        return "unavailable"
    finally:
        client.close()
