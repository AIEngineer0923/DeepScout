# Modern Agent Engineering in DeepScout

Public project document. Status: **IMPLEMENTED** | **FOUNDATION** | **DEFERRED** | **REJECTED**

## 2026 Agent Engineering Matrix

| Technique | Status | Why |
|---|---|---|
| Context engineering | FOUNDATION | `ContextAssembly` selects phase-scoped inputs only |
| Working memory | FOUNDATION | `WorkingMemory` bounds recent tool summaries per run |
| Long-term memory | DEFERRED | Postgres holds run state; no generic memory table yet |
| Semantic memory | DEFERRED | Requires validated write pipeline |
| Episodic memory | DEFERRED | Future cross-run learning |
| Procedural memory | DEFERRED | Prompts live in code, not self-modifying store |
| History compaction | DEFERRED | LangSmith audit trail; compaction later |
| Prompt/context caching | FOUNDATION | Provider capability hooks; no blind caching |
| Application caching | DEFERRED | Redis reserved; no search/fetch cache in Phase 3 |
| Token accounting | FOUNDATION | Budget ledger + tool/iteration counters |
| Token optimization | FOUNDATION | Bounded context assembly; phase budgets planned |
| Model routing | DEFERRED | Single configured model per run in Phase 3 |
| Thinking/reasoning effort | FOUNDATION | Provider layer owns Gemini thinking levels |
| Tool result compression | FOUNDATION | Search normalized + top-N persisted as candidates |
| Self-correction | DEFERRED | Domain invariant validation only |
| Reflection | DEFERRED | No automatic policy mutation |
| Trace-driven learning | DEFERRED | LangSmith traces captured; eval loop later |
| Evaluation | DEFERRED | Metrics defined; datasets in later phase |
| Retrieval optimization | DEFERRED | pgvector Phase 5 |
| Reranking | DEFERRED | Pipeline hook planned |
| Knowledge compaction / wiki memory | DEFERRED | Documented alternative to raw RAG |
| Confidence calibration | DEFERRED | Qualitative statuses preferred over fake floats |
| Uncertainty | FOUNDATION | `insufficient_evidence` terminal question state |
| Multi-agent specialization | IMPLEMENTED | Planner vs research phase separation |
| Parallelism | DEFERRED | Sequential iteration in Phase 3 |
| Checkpointing | FOUNDATION | Postgres run state is resume authority |
| HITL | DEFERRED | Hooks planned for high-impact decisions |
| Observability | IMPLEMENTED | LangSmith phases + typed domain events |
| Retries | FOUNDATION | Provider max_retries; bounded orchestrator failure paths |
| Fallback models | DEFERRED | No silent model swap |

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

## Caching separation

- **Application cache (Redis)**: DEFERRED — ephemeral dedupe/search cache later
- **Provider prompt cache**: FOUNDATION — capability flags only
- **Agent memory**: DEFERRED — distinct from both caches above
