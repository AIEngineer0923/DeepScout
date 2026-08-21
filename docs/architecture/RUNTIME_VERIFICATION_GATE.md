# Runtime Verification Gate — August 2026

## Documentation sources verified (architecture-impacting)

| Source | Topics |
|--------|--------|
| LangChain OSS Python | structured output, tool calling, agents, usage metadata |
| LangGraph | StateGraph, PostgresSaver(ConnectionPool), durability=sync, thread_id, interrupt/resume |
| LangSmith | datasets, evaluate(), client.evaluators.create, run rules REST attach |
| Google Gemini API | usage_metadata, structured output, system instruction precedence |
| OpenAI / Anthropic docs | provider abstraction parity, usage fields |

## Authority model

| Layer | Source of truth |
|-------|-----------------|
| Domain state | PostgreSQL (`ResearchStore`) — ResearchRun, tasks, evidence, budget, usage |
| LangGraph execution checkpoint | `PostgresSaver` over `psycopg_pool.ConnectionPool` (autocommit). Not domain authority. |
| Global lifecycle | `ResearchOrchestrator` |

Resume idempotency: completed `ResearchTask` rows are not re-executed; LangGraph thread `{run_id}:{task_id}` resumes from checkpoint without duplicate search when graph already completed.

## Gate commands (local only)

```bash
uv run pytest -m "not integration" -q
uv run pytest -m "integration and postgres" tests/test_runtime_gate_live.py -q
uv run python scripts/langsmith_trajectory.py
uv run python scripts/langsmith_online.py
```

## Checkpoint hang root cause

`PostgresSaver.from_conn_string()` yields **one** psycopg connection. Concurrent
workers plus SQLAlchemy sessions could block on that connection during `setup()`.

Fix: `PostgresSaver(ConnectionPool(..., kwargs={"autocommit": True, "prepare_threshold": 0}))`.
Default `RESEARCH_DURABLE_LANGGRAPH_CHECKPOINT=true`.

Guarantee: at-least-once worker execution with domain idempotency (completed tasks
are not re-run; search node skips if `search_results` already exist). Not exactly-once
for in-flight HTTP.

## In-flight cancellation

Tavily/httpx cannot hard-abort an already in-flight request. Cancellation is checked
before/after graph nodes and before later phases. Returned in-flight results are
discarded when the run is cancelled; no further spend is scheduled.

See prompt §48: `IMPLEMENTED` ≠ `LIVE_VERIFIED`. Live gate requires integration tests + workspace verification.
