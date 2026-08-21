# ADR-007: Budget exhaustion vs finalization reserve

**Status:** Accepted  
**Date:** 2026-08-21

## Context

ResearchBudget stops further search/source acquisition. Previously, raising
`BudgetExhaustedError` skipped synthesis and report even when sources/evidence
already existed.

## Decision

Option B:

- Research spending (iterations, tool calls, sources) remains a hard stop.
- A bounded deterministic finalization path still runs fetch/extract/verify/critic/synthesis/report
  against **already collected** artifacts.
- The run terminal status remains `budget_exhausted` so the UI does not claim
  a fully completed research loop.
- Setting `RESEARCH_FINALIZE_ON_BUDGET_EXHAUSTED=false` restores the old skip.

Finalization must not perform new web search. Token usage from synthesis still
counts, but cannot reopen the research worker loop.

## Consequences

- Users get a provenance-backed report from partial collections.
- Cost after exhaustion is limited to remaining LLM synthesis/report work.
- Tests must accept `budget_exhausted` with optional report presence.
