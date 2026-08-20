# Architecture Overview

DeepScout is a monorepo production-first system for autonomous, source-aware research.

## Layers

```text
┌─────────────────────────────────────────────────────────┐
│  apps/web (Next.js)          SSE / REST                 │
├─────────────────────────────────────────────────────────┤
│  apps/api (FastAPI)          HTTP boundary, streaming   │
├─────────────────────────────────────────────────────────┤
│  libs/research               Orchestrator + phases      │
│  libs/core                   Domain, budgets, schemas   │
│  libs/providers              LLM + embedding factory    │
│  libs/retrieval              RAG pipeline               │
│  libs/security               Fetch guard, sanitization  │
│  libs/observability          LangSmith tagging          │
├─────────────────────────────────────────────────────────┤
│  PostgreSQL + pgvector       Evidence graph + vectors   │
│  Redis                       Cache, rate limits, jobs   │
└─────────────────────────────────────────────────────────┘
```

## Key decisions

| ADR | Decision |
|---|---|
| [ADR-001](adr/ADR-001-monorepo-production-first.md) | Monorepo production-first |
| [ADR-002](adr/ADR-002-langchain-agent-runtime.md) | LangChain as agent runtime, custom orchestrator |
| [ADR-003](adr/ADR-003-multi-provider-factory.md) | Multi-provider LLM factory |
| [ADR-004](adr/ADR-004-bounded-research-loop.md) | Bounded research loop |
| [ADR-005](adr/ADR-005-sse-streaming.md) | SSE for API streaming |
| [ADR-006](adr/ADR-006-tavily-search-adapter.md) | Tavily as first WebSearchProvider |

## Related docs

- [Research Lifecycle](RESEARCH_LIFECYCLE.md)
- [Agent Architecture](AGENT_ARCHITECTURE.md)
- [Evidence Graph](EVIDENCE_GRAPH.md)
- [Provider Architecture](PROVIDER_ARCHITECTURE.md)
- [Data Model](DATA_MODEL.md)
- [Threat Model](../threat-model/THREAT_MODEL.md)
