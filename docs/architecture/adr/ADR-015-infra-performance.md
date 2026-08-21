# ADR-015: Performance closure, Redis, and dedicated graph store

Status: Accepted  
Date: 2026-08-21

## Context

MODE A already uses PostgreSQL as the durable authority for jobs, events, RAG, Wiki, and evidence relations. Redis exists in Compose as an optional health probe (`redis_required=false`). The evidence graph is relational. Exact pgvector scans are the default.

This ADR records lab measurements (`scripts/infra_decision_lab.py`, `LAB_NETWORK_SIMULATION` / synthetic corpora) rather than résumé-driven infrastructure.

## Decisions

| Topic | Decision |
|---|---|
| Redis SSE/fanout | **REJECTED_BY_MEASUREMENT** — LISTEN/NOTIFY + durable `run_events` is enough for MODE A |
| Redis cache / queue / locks / rate-limit | **REJECTED** — PostgreSQL already owns jobs, leases, events, and budgets |
| Redis Pub/Sub vs Streams | Pub/Sub is not durable replay; Streams would duplicate `run_events` |
| PostgreSQL LISTEN/NOTIFY | **IMPLEMENTED_DEFAULT** wake-up in front of 0.4s/0.8s poll fallback |
| pgvector ANN / HNSW | **KEEP EXACT** unless lab exact@10k exceeds ~80ms |
| Neo4j / dedicated graph DB | **REJECTED_BY_MEASUREMENT** — bounded recursive CTE 1–3 hop is sufficient at MODE A scale |
| Report token streaming | **EVALUATED_AND_DEFERRED** — structured report must validate before user-visible text |
| Subagent streaming | **FUTURE_GATED** (`max_depth=1`) |

## Failure policy

LISTEN/NOTIFY outage falls back to adaptive DB poll. Research state is unchanged. Redis remaining down does not affect readiness.

If a dedicated graph DB is ever adopted, it must be a rebuildable projection of PostgreSQL evidence, never a second authority.
