# ADR-001: Monorepo production-first

**Status:** Accepted (Phase 0)

## Context

DeepScout must evolve directly into a publishable OSS product, not a throwaway prototype.

## Decision

Use a monorepo with separated apps (`api`, `web`) and shared libs (`core`, `research`, `providers`, …).

## Consequences

- Clear bounded contexts and testability
- Single CI/CD pipeline
- Requires disciplined module boundaries (enforced in Phase 2+)
