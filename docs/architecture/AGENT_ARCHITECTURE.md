# Agent Architecture

## Two-loop model

| Loop | Owner | Responsibility |
|---|---|---|
| **Outer** | DeepScout orchestrator | State machine, budgets, persistence, provenance |
| **Inner** | LangChain `create_agent` | Model ↔ tools within a single phase |

## Phase agents (LangChain)

Each phase may use a dedicated agent configuration:

```python
# Conceptual — implemented Phase 3+
agent = create_agent(
    model=provider.chat(model=settings.llm_model),
    tools=phase_tools,
    middleware=[BudgetMiddleware, PhaseToolFilter, TracingMiddleware],
    context_schema=ResearchRuntimeContext,
    response_format=ToolStrategy(PhaseOutputSchema),
)
```

## Middleware stack

1. `BudgetMiddleware` — block when ledger exhausted
2. `PhaseToolFilterMiddleware` — allowlist tools per phase
3. `TracingMiddleware` — LangSmith metadata (`run_id`, `phase`)
4. Structured output enforcement per phase

## Tool registry

Tools live in `libs/research/tools/` with a registry keyed by phase.
Web search uses `WebSearchProvider` interface — not Tavily directly.

## Contributor learning path (Phase 1+)

For each new LangChain concept introduced during development:

**LEARN → IMPLEMENT → VERIFY → EXPLAIN**

Each concept should be documented with purpose, location in the codebase, and
how to test it independently.

## What is NOT exposed

- Raw chain-of-thought
- Unverified claims as UI facts
- Provider-specific code outside `libs/providers/`
