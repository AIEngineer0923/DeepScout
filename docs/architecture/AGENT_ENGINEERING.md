# Modern Agent Engineering in DeepScout

Public project document. Status: **IMPLEMENTED** | **FOUNDATION** | **DEFERRED** | **REJECTED**

## 2026 Agent Engineering Matrix

| Technique | Status | Why |
|---|---|---|
| Context engineering | IMPLEMENTED | `ContextAssembly` budgets, isolation, compaction |
| Working memory | FOUNDATION | `WorkingMemory` bounds recent tool summaries per run |
| Long-term memory | DEFERRED | Postgres holds run state; no generic memory table yet |
| Semantic memory | DEFERRED | Requires validated write pipeline |
| Episodic memory | DEFERRED | Future cross-run learning |
| Procedural memory | FOUNDATION | Builtin SKILL.md catalog; router selects, never self-promotes |
| History compaction | FOUNDATION | Deterministic retrieved-blob compaction; never evidence-as-summary |
| Prompt/context caching | FOUNDATION | Provider capability hooks; no blind caching |
| Application caching | REJECTED (MODE A) | Redis probe-only; Postgres owns jobs/checkpoints |
| Token accounting | IMPLEMENTED | Provider metadata recorded; UNKNOWN never coerced to 0; evaluator usage excluded from application totals |
| Token optimization | FOUNDATION | Bounded context assembly; phase budgets planned |
| Model routing | IMPLEMENTED | Capability registry + role policies; optional configured fallback |
| Thinking/reasoning effort | FOUNDATION | Provider layer owns Gemini thinking levels |
| Tool result compression | FOUNDATION | Search normalized + top-N persisted as candidates |
| Self-correction | IMPLEMENTED | Deterministic critic + bounded re-verify; LangGraph correction graph is unit-tested only |
| Evaluation | IMPLEMENTED | Deterministic evaluators executed against persisted runs; LangSmith offline/online wiring |
| Parallelism | IMPLEMENTED | Ready-task fan-out with max concurrency |
| Checkpointing | IMPLEMENTED | Postgres LangGraph ConnectionPool checkpointer + domain task reclaim |
| Retries | IMPLEMENTED | Central `retry.py` for transient 429/5xx/network; security failures never retry |
| Reflection | DEFERRED | No automatic policy mutation without promotion gate |
| Trace-driven learning | FOUNDATION | Learning cases + deterministic loop gate; episodic memory still deferred |
| Retrieval optimization | IMPLEMENTED | Phase 5 hybrid FTS + pgvector |
| Reranking | IMPLEMENTED | Deterministic rerank + RRF |
| Knowledge compaction / wiki memory | IMPLEMENTED | Run-scoped compiled Wiki (ADR-009) |
| Confidence calibration | DEFERRED | Qualitative statuses preferred over fake floats |
| Uncertainty | FOUNDATION | `insufficient_evidence` terminal question state |
| Multi-agent specialization | IMPLEMENTED | Planner vs research worker vs critic/synthesis/report |
| HITL | IMPLEMENTED | ADR-011 durable reviews; budget-extension pause |
| Observability | IMPLEMENTED | LangSmith phases + typed domain events |
| Fallback models | IMPLEMENTED_OPTIONAL | Capability + privacy + health gated; no silent downgrade |

## Core loops

| Topic | Status | Why |
|---|---|---|
| Outer deterministic orchestrator | IMPLEMENTED | `ResearchOrchestrator` owns lifecycle, budget, termination |
| Inner LangChain agent loop | IMPLEMENTED | Planner structured output; research uses tools via adapter |
| Tool permissions by phase | IMPLEMENTED | Planner has no web tools; research uses search only |

## Safety

| Topic | Status | Why |
|---|---|---|
| Prompt injection boundary | IMPLEMENTED | External content labeled untrusted DATA in context assembly |
| SSRF secure fetch | FOUNDATION | Scheme/DNS/IP/redirect policy; connection pinning limitation documented in code |
| Budget / denial-of-wallet | IMPLEMENTED | Pre-tool budget gate + atomic ledger |

## Execution

| Topic | Status | Why |
|---|---|---|
| Background execution | IMPLEMENTED | FastAPI `BackgroundTasks` + 202 execute endpoint |
| BullMQ / Celery queue | REJECTED | Python backend; defer worker queue until scale requires it |

- **LangGraph correction graph** (`graphs/correction.py`): KEEP as a unit-tested bounded validate→critic graph. Do **not** put it on the production hot path. Production uses deterministic critic + at most one re-verify in `ResearchOrchestrator`. The graph currently adds no extra statefulness beyond that loop.

- **Application cache (Redis)**: DEFERRED — ephemeral dedupe/search cache later
- **Provider prompt cache**: FOUNDATION — capability flags only
- **Agent memory**: DEFERRED — distinct from both caches above
