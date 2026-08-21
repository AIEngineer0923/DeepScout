# ADR-017: Product completion — semantic planner, follow-up, source policy, monitors, knowledge UI, run diff, LISTEN/NOTIFY, RUM

Status: Accepted  
Date: 2026-08-21

## Context

After PR #35, remaining MODE A product/runtime gaps were: false-simple planner classification, follow-up research, source pin/exclude, scheduled monitors, knowledge browsing, run comparison, demonstrated LISTEN/NOTIFY wake, and field Core Web Vitals.

## Decision

- Keep PostgreSQL as the only source of truth. Redis and Neo4j remain rejected for MODE A.
- Add a bounded semantic dependency validator (one extra structured LLM call) after Planner v2, then existing deterministic `repair_plan`.
- Follow-up and monitor executions are new `ResearchRun` rows with `lineage_kind`; historical runs are immutable.
- Source PIN/EXCLUDE persist as typed rows and filter search + hybrid retrieval. Pin does not skip verification.
- Monitors use `FOR UPDATE SKIP LOCKED` leases and timezone-aware next-run math. No Celery/Redis.
- Knowledge UI reads existing Wiki tables. Graph traversal stays the bounded PostgreSQL CTE (max 3 hops).
- LISTEN/NOTIFY fires on AUTOCOMMIT after `run_events` commit. Poll remains fallback. Last-Event-ID remains replay.
- Field RUM stores LCP/INP/CLS/TTFB/FCP in PostgreSQL with route allowlisting and rate limits. No research text.

## Consequences

Planner v1 skips the validator. Wiki remains derived, not evidence. Lab network profiles are not field cellular data.
