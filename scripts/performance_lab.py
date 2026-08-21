#!/usr/bin/env python3
"""Local performance lab: API/DB timings without live LLM spend."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from deepscout_core.settings import get_settings
from deepscout_persistence.session import get_engine, get_session_factory
from deepscout_persistence.store import ResearchStore
from sqlalchemy import text


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((p / 100) * (len(ordered) - 1)))))
    return ordered[index]


def main() -> int:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    rows, total = store.list_runs(limit=5)
    samples: list[float] = []
    for _ in range(8):
        started = time.perf_counter()
        store.list_runs(limit=20)
        samples.append((time.perf_counter() - started) * 1000)
    plans = {}
    with engine.connect() as conn:
        plans["fts"] = str(
            conn.execute(
                text(
                    "EXPLAIN (FORMAT TEXT) SELECT c.id FROM document_chunks c "
                    "WHERE c.research_run_id = '00000000-0000-0000-0000-000000000000' "
                    "AND c.search_vector @@ plainto_tsquery('simple', 'battery') LIMIT 8"
                )
            ).all()
        )
        plans["events"] = str(
            conn.execute(
                text(
                    "EXPLAIN (FORMAT TEXT) SELECT sequence FROM run_events "
                    "WHERE research_run_id = '00000000-0000-0000-0000-000000000000' "
                    "AND sequence > 0 ORDER BY sequence"
                )
            ).all()
        )
    session.close()
    payload = {
        "measured_at": datetime.now(UTC).isoformat(),
        "list_runs_total": total,
        "list_runs_sample": len(rows),
        "list_runs_ms": {
            "p50": _percentile(samples, 50),
            "p75": _percentile(samples, 75),
            "p95": _percentile(samples, 95),
            "n": len(samples),
        },
        "explain": plans,
        "pool": {"pool_size": 8, "max_overflow": 16},
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
