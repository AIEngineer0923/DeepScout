"""LangGraph checkpointer factory.

DeepScout PostgreSQL domain tables remain the source of truth for ResearchRun,
ResearchTask, Source, Evidence, Budget, and Usage.

LangGraph checkpoints store only worker graph execution snapshots so a graph can
resume after process interruption. They must not be treated as domain state.

Root cause of the previous hang: PostgresSaver.from_conn_string() yields a single
psycopg Connection. Concurrent ThreadPoolExecutor workers serialized on that
connection and could deadlock with SQLAlchemy sessions. Official production
pattern is PostgresSaver(ConnectionPool) with autocommit.
"""

from __future__ import annotations

import logging
import threading
from functools import lru_cache
from urllib.parse import urlparse, urlunparse

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_POOL = None
_POSTGRES_CHECKPOINTER: object | None = None


@lru_cache(maxsize=1)
def _memory_checkpointer() -> MemorySaver:
    return MemorySaver()


def psycopg_conninfo(database_url: str) -> str:
    """Convert SQLAlchemy URLs to a psycopg conninfo string. Never log the result."""
    raw = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    raw = raw.replace("postgresql+psycopg2://", "postgresql://", 1)
    parsed = urlparse(raw)
    return urlunparse(parsed._replace(scheme="postgresql"))


def get_worker_checkpointer(*, database_url: str | None = None, durable: bool = True):
    """Return a Postgres ConnectionPool checkpointer when durable, else MemorySaver."""
    if not durable or not database_url:
        return _memory_checkpointer()

    global _POOL, _POSTGRES_CHECKPOINTER
    with _LOCK:
        if _POSTGRES_CHECKPOINTER is not None:
            return _POSTGRES_CHECKPOINTER
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg_pool import ConnectionPool
        except ImportError:
            logger.warning("postgres_checkpointer_unavailable_falling_back_to_memory")
            return _memory_checkpointer()

        conninfo = psycopg_conninfo(database_url)
        pool = ConnectionPool(
            conninfo=conninfo,
            min_size=1,
            max_size=8,
            timeout=10.0,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
            },
            open=True,
        )
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()
        _POOL = pool
        _POSTGRES_CHECKPOINTER = checkpointer
        logger.info("langgraph_postgres_checkpointer_ready")
        return checkpointer


def reset_worker_checkpointer_cache() -> None:
    """Dispose the process-global pool so tests can simulate process restart."""
    global _POOL, _POSTGRES_CHECKPOINTER
    with _LOCK:
        if _POOL is not None:
            try:
                _POOL.close()
            except Exception:
                logger.debug("checkpointer_pool_close_failed", exc_info=True)
        _POOL = None
        _POSTGRES_CHECKPOINTER = None
        _memory_checkpointer.cache_clear()
