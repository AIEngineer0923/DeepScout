"""LangGraph checkpointer factory — durable Postgres when configured."""

from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.memory import MemorySaver

_POSTGRES_CM = None
_POSTGRES_CHECKPOINTER: object | None = None


@lru_cache(maxsize=1)
def _memory_checkpointer() -> MemorySaver:
    return MemorySaver()


def get_worker_checkpointer(*, database_url: str | None = None, durable: bool = True):
    """Return Postgres checkpointer when URL available, else MemorySaver."""
    if not durable or not database_url:
        return _memory_checkpointer()
    global _POSTGRES_CM, _POSTGRES_CHECKPOINTER
    if _POSTGRES_CHECKPOINTER is not None:
        return _POSTGRES_CHECKPOINTER
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError:
        return _memory_checkpointer()

    conn = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    conn = conn.replace("postgresql+psycopg2://", "postgresql://", 1)
    _POSTGRES_CM = PostgresSaver.from_conn_string(conn)
    checkpointer = _POSTGRES_CM.__enter__()
    checkpointer.setup()
    _POSTGRES_CHECKPOINTER = checkpointer
    return checkpointer


def reset_worker_checkpointer_cache() -> None:
    global _POSTGRES_CM, _POSTGRES_CHECKPOINTER
    if _POSTGRES_CM is not None and _POSTGRES_CHECKPOINTER is not None:
        _POSTGRES_CM.__exit__(None, None, None)
    _POSTGRES_CM = None
    _POSTGRES_CHECKPOINTER = None
    _memory_checkpointer.cache_clear()
