"""Shared PostgreSQL helpers for integration tests."""

from __future__ import annotations

import os

from deepscout_persistence.session import get_engine
from sqlalchemy import text


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://deepscout:deepscout@localhost:5432/deepscout",
    )


def postgres_available() -> bool:
    try:
        engine = get_engine(database_url())
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
