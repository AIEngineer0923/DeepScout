# ADR-001: Hybrid Multi-Agent Research Architecture

## Status
Accepted — implemented in Phase 4 foundation.

## Context
DeepScout requires deterministic global orchestration, parallel research workers,
durable execution, PostgreSQL authority, LangSmith observability, and bounded
local agent loops.

## Decision
Use a **hybrid architecture**:

| Layer | Owner | Technology |
|---|---|---|
| Global supervisor | `ResearchOrchestrator` | Deterministic Python |
| Persistence / budget | PostgreSQL + `ResearchStore` | SQLAlchemy |
| Durable execution | `research_jobs` lease queue | PostgreSQL |
| Task DAG | `research_tasks` + `TaskGraph` | Deterministic scheduler |
| Parallel workers | `ResearchWorkerPool` | Thread pool fan-out/fan-in |
| Local worker graph | `langgraph_worker` | LangGraph subgraph |
| Planner / critics (future) | Structured LangChain calls | Provider-neutral factory |
| Tracing | LangSmith `@traceable` | Phase/worker correlated spans |

LangGraph does **not** own global lifecycle, budgets, or termination.

## Consequences
- Resume authority remains PostgreSQL (`research_tasks`, checkpoints, jobs).
- LangGraph checkpoint store may be added later without replacing domain state.
- Celery/RQ rejected; PostgreSQL job leasing is sufficient for current scale.
