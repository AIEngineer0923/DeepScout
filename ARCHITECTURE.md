# DeepScout Architecture

DeepScout is a monorepo production-first system for autonomous, source-aware research.

## System context

```text
┌──────────────┐     SSE/REST      ┌──────────────┐
│  apps/web    │ ◄──────────────► │  apps/api    │
│  Next.js     │                   │  FastAPI     │
└──────────────┘                   └──────┬───────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
             libs/research          libs/providers         libs/security
             (orchestrator)         (LLM factory)         (fetch guard)
                    │                     │                     │
                    └──────────┬──────────┴──────────┬──────────┘
                               ▼                     ▼
                        PostgreSQL              Redis
                        + pgvector
                               │
                        LangSmith traces
```

## Core principles

1. **Explicit orchestrator** — Python state machine owns phases, budgets, and termination
2. **LangChain per phase** — `create_agent` for plan, research, extract, critic — not one infinite loop
3. **Evidence graph** — claims linked to source snapshots via evidence quotes
4. **Multi-provider** — `LLM_PROVIDER` + factory; no provider imports in domain code
5. **Pluggable search** — `WebSearchProvider`; Tavily is v1 adapter only
6. **Secure ingestion** — SSRF-safe fetch before Internet content enters prompts
7. **Observable** — LangSmith spans per phase; no chain-of-thought in product UI

## Research lifecycle

```text
PLAN → RESEARCH → COLLECT → EXTRACT → EVIDENCE → VERIFY → CONTRADICTIONS
  → SUFFICIENCY → [iterate if budget ok] → CRITIC → DECISION → REPORT
```

Details: [docs/architecture/RESEARCH_LIFECYCLE.md](docs/architecture/RESEARCH_LIFECYCLE.md)

## Bounded execution

`ResearchBudget` enforced in orchestrator code before each phase:

| Limit | Default |
|---|---|
| iterations | 5 |
| wall time | 900s |
| sources | 40 |
| tool calls | 80 |

## Module map (Phase 1+)

| Module | Responsibility |
|---|---|
| `libs/core` | Domain schemas, budgets, policies |
| `libs/research` | Orchestrator, phases, tools |
| `libs/providers` | LLM + embedding + search adapters |
| `libs/retrieval` | Loaders, splitters, pgvector |
| `libs/security` | URL policy, sanitization |
| `libs/observability` | LangSmith tagging |

## Architecture decisions

| ADR | Summary |
|---|---|
| [ADR-001](docs/architecture/adr/ADR-001-monorepo-production-first.md) | Monorepo production-first |
| [ADR-002](docs/architecture/adr/ADR-002-langchain-agent-runtime.md) | LangChain + custom orchestrator |
| [ADR-003](docs/architecture/adr/ADR-003-multi-provider-factory.md) | Multi-provider factory |
| [ADR-004](docs/architecture/adr/ADR-004-bounded-research-loop.md) | Bounded research loop |
| [ADR-005](docs/architecture/adr/ADR-005-sse-streaming.md) | SSE streaming |
| [ADR-006](docs/architecture/adr/ADR-006-tavily-search-adapter.md) | Tavily search adapter |

## Further reading

| Topic | Document |
|---|---|
| Agent design (LangChain) | [docs/architecture/AGENT_ARCHITECTURE.md](docs/architecture/AGENT_ARCHITECTURE.md) |
| Evidence graph | [docs/architecture/EVIDENCE_GRAPH.md](docs/architecture/EVIDENCE_GRAPH.md) |
| Provider abstraction | [docs/architecture/PROVIDER_ARCHITECTURE.md](docs/architecture/PROVIDER_ARCHITECTURE.md) |
| RAG pipeline | [docs/architecture/RAG_PIPELINE.md](docs/architecture/RAG_PIPELINE.md) |
| Secure fetch | [docs/architecture/SECURE_FETCH_PIPELINE.md](docs/architecture/SECURE_FETCH_PIPELINE.md) |
| LangSmith | [docs/architecture/LANGSMITH_OBSERVABILITY.md](docs/architecture/LANGSMITH_OBSERVABILITY.md) |
| Data model | [docs/architecture/DATA_MODEL.md](docs/architecture/DATA_MODEL.md) |
| API / SSE | [docs/architecture/API_SSE_ARCHITECTURE.md](docs/architecture/API_SSE_ARCHITECTURE.md) |
| Threat model | [docs/threat-model/THREAT_MODEL.md](docs/threat-model/THREAT_MODEL.md) |

## OSS contributor path

External contributors can clone, configure `.env`, run Docker, execute tests, and
contribute using only public repository tooling — no maintainer-private infrastructure
required.
