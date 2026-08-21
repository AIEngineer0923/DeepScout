"""PostgreSQL LISTEN/NOTIFY wake-up for durable run_events (Postgres remains the log)."""

from __future__ import annotations

import time
from uuid import UUID

CHANNEL = "deepscout_run_events"


def listen_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )


class NotifyWaiter:
    """Long-lived LISTEN connection. Falls back to sleep if listen fails."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._conn = None

    def wait(self, run_id: UUID, timeout_s: float) -> bool:
        deadline = time.monotonic() + max(0.05, timeout_s)
        remaining = timeout_s
        try:
            import psycopg

            if self._conn is None:
                self._conn = psycopg.connect(
                    listen_dsn(self._database_url),
                    autocommit=True,
                    connect_timeout=2,
                )
                self._conn.execute(f"LISTEN {CHANNEL}")
            for notify in self._conn.notifies(timeout=remaining, stop_after=1):
                if str(notify.payload) == str(run_id):
                    return True
            return False
        except Exception:
            self.close()
            leftover = deadline - time.monotonic()
            if leftover > 0:
                time.sleep(leftover)
            return False

    def close(self) -> None:
        conn = self._conn
        self._conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def wait_for_run_notify(database_url: str, run_id: UUID, *, timeout_s: float) -> bool:
    waiter = NotifyWaiter(database_url)
    try:
        return waiter.wait(run_id, timeout_s)
    finally:
        waiter.close()
