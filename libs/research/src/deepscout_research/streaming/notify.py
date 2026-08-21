"""PostgreSQL LISTEN/NOTIFY wake-up for durable run_events (Postgres remains the log)."""

from __future__ import annotations

import time
from uuid import UUID

from sqlalchemy import text

CHANNEL = "deepscout_run_events"


def listen_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )


def notify_run_events(bind, run_ids: set[UUID]) -> None:
    """Fire NOTIFY on a dedicated AUTOCOMMIT connection after the event transaction commits.

    NOTIFY is a wake signal only. run_events remains the durable log.
    """
    if not run_ids:
        return
    with bind.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        for run_id in run_ids:
            conn.execute(text("SELECT pg_notify(:c, :p)"), {"c": CHANNEL, "p": str(run_id)})


class NotifyWaiter:
    """Long-lived LISTEN connection. Falls back to sleep if listen fails."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._conn = None

    def wait(self, run_id: UUID, timeout_s: float) -> bool:
        deadline = time.monotonic() + max(0.05, timeout_s)
        try:
            import psycopg

            if self._conn is None:
                self._conn = psycopg.connect(
                    listen_dsn(self._database_url),
                    autocommit=True,
                    connect_timeout=2,
                )
                self._conn.execute(f"LISTEN {CHANNEL}")
            remaining = max(0.05, deadline - time.monotonic())
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
