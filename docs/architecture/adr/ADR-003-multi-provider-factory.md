# ADR-003: Multi-provider LLM factory

**Status:** Accepted (Phase 0)

## Context

DeepScout must support Google, OpenAI, and Anthropic without provider lock-in.

## Decision

`libs/providers/` factory driven by `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDING_*` env vars.
Model IDs centralized in `defaults.py` after official doc verification in Phase 1.

## Consequences

- Swappable providers via config only
- Factory must be tested with fakes in unit tests
