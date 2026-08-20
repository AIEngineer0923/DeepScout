# ADR-004: Bounded research loop

**Status:** Accepted (Phase 0)

## Context

Unbounded autonomous loops risk cost, latency, and unreliable termination.

## Decision

`ResearchBudget` enforced by orchestrator code before each phase/iteration.

## Consequences

- Predictable cost and runtime
- May produce partial reports when budget exhausted (explicit in UI)
