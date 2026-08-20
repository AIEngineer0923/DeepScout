# Runtime Verification Gate — August 2026

## Documentation sources verified (architecture-impacting)

| Source | Topics |
|--------|--------|
| LangChain OSS Python | structured output, tool calling, agents, usage metadata |
| LangGraph | StateGraph, checkpoint/resume, conditional edges, Send parallelism |
| LangSmith | datasets, experiments, tracing metadata, evaluate API |
| Google Gemini API | usage_metadata, structured output, system instruction precedence |
| OpenAI / Anthropic docs | provider abstraction parity, usage fields |

## Authority model

| Layer | Source of truth |
|-------|-----------------|
| Domain state | PostgreSQL (`ResearchStore`) |
| LangGraph execution checkpoint | `langgraph-checkpoint-postgres` when `DATABASE_URL` set; else MemorySaver (dev/test) |
| Global lifecycle | `ResearchOrchestrator` |

Resume idempotency: completed `ResearchTask` rows are not re-executed; LangGraph thread `{run_id}:{task_id}` resumes from checkpoint without duplicate search when graph already completed.

## Gate commands (local only)

```bash
uv run pytest -m "not integration" -q
uv run pytest -m "integration and postgres" tests/test_runtime_gate_live.py -q
uv run python scripts/langsmith_bootstrap.py
uv run python scripts/langsmith_experiment.py
```

## Verified on branch `feat/runtime-eval-gate` (2026-08-21)

| Check | Status |
|-------|--------|
| Unit tests (`not integration`) | TEST_VERIFIED — 85 passed |
| Live full pipeline E2E | LIVE_VERIFIED — `test_runtime_gate_full_pipeline` |
| Baseline vs multi-agent | TEST_VERIFIED — `test_runtime_gate_baseline_vs_multi_agent_metrics` |
| LangSmith dataset bootstrap | LIVE_VERIFIED — `deepscout-baseline-v1` (9 examples) |
| LangSmith offline experiment | LIVE_VERIFIED — `deepscout-gate-YYYYMMDD-*` with deterministic evaluator |
| EU workspace endpoint | Required — set via `configure_langsmith_env()` from Settings |
| Postgres LangGraph checkpoint (opt-in) | BLOCKED — `RESEARCH_DURABLE_LANGGRAPH_CHECKPOINT=true` hangs on setup |
| Correction LangGraph (`graphs/correction.py`) | IMPLEMENTED — production path uses orchestrator re-verify loop instead |

## Correction wiring

Production critic correction uses deterministic re-verify in `ResearchOrchestrator._run_post_research_phases` (max 1 round). The standalone `graphs/correction.py` LangGraph remains for unit tests and future artifact-specific correction; it is **not** on the hot path by design until synthesis/report LLM correction is required.

## Snapshot text safety

PDF payloads and NUL bytes are stripped in `fetch/content_text.py` before PostgreSQL persistence — required for live evidence path.

See prompt §48: `IMPLEMENTED` ≠ `LIVE_VERIFIED`. Live gate requires integration tests + workspace verification.
