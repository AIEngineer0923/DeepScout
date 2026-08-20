# ADR-002: LangChain as agent runtime

**Status:** Accepted (Phase 0)

## Context

Need agentic capabilities (tools, middleware, structured output, tracing) without building from scratch.

## Decision

LangChain Python `create_agent` for phase-local agents; custom Python orchestrator for global workflow and budgets.

## Consequences

- Faster iteration on agent patterns
- Must learn LangChain deeply (learning mode)
- Two-loop mental model required for contributors
