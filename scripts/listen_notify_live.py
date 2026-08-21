#!/usr/bin/env python3
"""Live LISTEN/NOTIFY wake proof. Poll timeout is 400ms; PASS requires wake first."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from deepscout_core.settings import get_settings
from deepscout_persistence.session import get_engine
from deepscout_research.streaming.notify import NotifyWaiter
from sqlalchemy import text

OUT = Path("libs/evaluation/data/listen_notify_live_v1.json")


def main() -> int:
    settings = get_settings()
    run_id = uuid.uuid4()
    waiter = NotifyWaiter(settings.database_url)
    started = time.perf_counter()
    import threading

    result = {"listen_woke": False, "wake_ms": None}

    def listen() -> None:
        t0 = time.perf_counter()
        result["listen_woke"] = waiter.wait(run_id, 1.2)
        result["wake_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    thread = threading.Thread(target=listen)
    thread.start()
    time.sleep(0.12)
    engine = get_engine(settings.database_url)
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT").execute(
            text("SELECT pg_notify('deepscout_run_events', :p)"),
            {"p": str(run_id)},
        )
    thread.join(timeout=3)
    waiter.close()
    payload = {
        "listen_woke": result["listen_woke"],
        "wake_ms": result["wake_ms"],
        "poll_fallback_ms": 400,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "pass": bool(result["listen_woke"] and (result["wake_ms"] or 999) < 400),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
