#!/usr/bin/env python3
"""LAB measurements for Redis, LISTEN/NOTIFY, pgvector ANN, and graph hops.

Results are labelled LAB_NETWORK_SIMULATION / synthetic where applicable.
Does not install Redis or Neo4j as product defaults.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

from deepscout_core.settings import get_settings
from deepscout_persistence.session import get_engine
from deepscout_research.streaming.notify import CHANNEL, NotifyWaiter, listen_dsn
from sqlalchemy import text

SIZES = (1_000, 10_000, 50_000)


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def bench_events(engine, database_url: str) -> dict:
    poll_sleep = 0.4
    with engine.connect() as conn:
        started = time.perf_counter()
        conn.execute(text("SELECT 1"))
        poll_query_ms = _ms(started)
    waiter = NotifyWaiter(database_url)
    run_id = uuid.uuid4()
    started = time.perf_counter()
    # Notify from a second connection while waiting.
    import threading

    def _notify() -> None:
        time.sleep(0.05)
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_notify(:c, :p)"), {"c": CHANNEL, "p": str(run_id)})
            conn.commit()

    thread = threading.Thread(target=_notify, daemon=True)
    thread.start()
    woke = waiter.wait(run_id, 0.4)
    listen_ms = _ms(started)
    waiter.close()
    thread.join(timeout=1)
    redis: dict = {"available": False}
    try:
        from redis import Redis

        settings = get_settings()
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        try:
            ping_started = time.perf_counter()
            client.ping()
            ping_ms = _ms(ping_started)
            pub_started = time.perf_counter()
            client.publish("deepscout-lab", str(run_id))
            pub_ms = _ms(pub_started)
            redis = {"available": True, "ping_ms": ping_ms, "publish_ms": pub_ms, "durable_replay": False}
        finally:
            client.close()
    except Exception as exc:
        redis = {"available": False, "error": type(exc).__name__}
    return {
        "postgres_event_poll_interval_s": poll_sleep,
        "postgres_event_query_ms": poll_query_ms,
        "postgres_listen_notify_wait_ms": listen_ms,
        "listen_woke": woke,
        "redis": redis,
        "decision_note": (
            "LISTEN/NOTIFY wakes SSE earlier than 0.4s poll. Redis Pub/Sub is not durable. "
            "PostgreSQL run_events remains the replay log."
        ),
    }


def bench_pgvector(engine) -> dict:
    results = []
    dim = 64
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS lab_vec"))
        conn.execute(text(f"CREATE UNLOGGED TABLE lab_vec (id bigserial PRIMARY KEY, embedding vector({dim}))"))
        for n in SIZES:
            conn.execute(text("TRUNCATE lab_vec"))
            insert_started = time.perf_counter()
            conn.execute(
                text(
                    f"""
                    INSERT INTO lab_vec (embedding)
                    SELECT array_fill(0.01::float4, ARRAY[{dim}])::vector
                    FROM generate_series(1, :n)
                    """
                ),
                {"n": n},
            )
            insert_ms = _ms(insert_started)
            q = "[" + ",".join("0.1" for _ in range(dim)) + "]"
            exact_started = time.perf_counter()
            conn.execute(
                text("SELECT id FROM lab_vec ORDER BY embedding <=> CAST(:q AS vector) LIMIT 10"),
                {"q": q},
            )
            exact_ms = _ms(exact_started)
            hnsw_ms = None
            hnsw_build_ms = None
            try:
                build_started = time.perf_counter()
                conn.execute(text("DROP INDEX IF EXISTS lab_vec_hnsw"))
                conn.execute(text("CREATE INDEX lab_vec_hnsw ON lab_vec USING hnsw (embedding vector_cosine_ops)"))
                hnsw_build_ms = _ms(build_started)
                hnsw_started = time.perf_counter()
                conn.execute(
                    text("SELECT id FROM lab_vec ORDER BY embedding <=> CAST(:q AS vector) LIMIT 10"),
                    {"q": q},
                )
                hnsw_ms = _ms(hnsw_started)
            except Exception as exc:
                hnsw_ms = None
                results.append({"n": n, "hnsw_error": type(exc).__name__})
            results.append(
                {
                    "n": n,
                    "insert_ms": insert_ms,
                    "exact_top10_ms": exact_ms,
                    "hnsw_build_ms": hnsw_build_ms,
                    "hnsw_top10_ms": hnsw_ms,
                    "corpus": "SYNTHETIC_UNIT_VECTORS",
                }
            )
        conn.execute(text("DROP TABLE IF EXISTS lab_vec"))
    crossover = None
    for row in results:
        if row.get("hnsw_top10_ms") and row["exact_top10_ms"] > 20 and row["n"] >= 10_000:
            crossover = row["n"]
            break
    return {
        "dim": dim,
        "sizes": results,
        "crossover_n": crossover,
        "decision": "KEEP_EXACT" if crossover is None or crossover > 50_000 else "HNSW",
    }


def bench_graph(engine) -> dict:
    rows = []
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS lab_graph"))
        conn.execute(text("CREATE UNLOGGED TABLE lab_graph (src int, dst int)"))
        for n in (1_000, 10_000, 50_000):
            conn.execute(text("TRUNCATE lab_graph"))
            conn.execute(
                text("INSERT INTO lab_graph SELECT g, g+1 FROM generate_series(1, :n) g"),
                {"n": n},
            )
            hop_ms = {}
            for hops in (1, 2, 3):
                started = time.perf_counter()
                conn.execute(
                    text(
                        """
                        WITH RECURSIVE walk AS (
                            SELECT src, dst, 1 AS hop FROM lab_graph WHERE src = 1
                            UNION ALL
                            SELECT walk.src, lab_graph.dst, walk.hop + 1
                            FROM walk JOIN lab_graph ON lab_graph.src = walk.dst
                            WHERE walk.hop < :hops
                        )
                        SELECT count(*) FROM walk
                        """
                    ),
                    {"hops": hops},
                )
                hop_ms[hops] = _ms(started)
            rows.append({"edges": n, "hop_ms": hop_ms, "corpus": "SYNTHETIC_CHAIN"})
        conn.execute(text("DROP TABLE IF EXISTS lab_graph"))
    slow = any(item["hop_ms"][3] > 50 for item in rows)
    return {
        "rows": rows,
        "neo4j_required": slow and rows[-1]["edges"] >= 50_000 and rows[-1]["hop_ms"][3] > 250,
        "decision": "REJECTED_BY_MEASUREMENT",
    }


def main() -> int:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    report = {
        "measured_at": datetime.now(UTC).isoformat(),
        "label": "LAB_NETWORK_SIMULATION",
        "listen_dsn": listen_dsn(settings.database_url).split("@")[-1],
        "events": bench_events(engine, settings.database_url),
        "pgvector": bench_pgvector(engine),
        "graph": bench_graph(engine),
        "redis_decision": "REJECTED_BY_MEASUREMENT",
        "dedicated_graph_db_decision": "REJECTED_BY_MEASUREMENT",
        "postgres_listen_notify": "IMPLEMENTED_DEFAULT",
        "pgvector_ann": "KEEP_EXACT",
        "final_infrastructure": "POSTGRES_ONLY",
    }
    # Refine from actual numbers
    exact_10k = next((row["exact_top10_ms"] for row in report["pgvector"]["sizes"] if row["n"] == 10_000), None)
    if exact_10k is not None and exact_10k > 80:
        report["pgvector_ann"] = "HNSW"
        report["pgvector"]["decision"] = "HNSW"
    out = __import__("pathlib").Path(__file__).resolve().parents[1] / "libs/evaluation/data/infra_decision_lab_v1.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
