# ADR-006: Tavily as first WebSearchProvider

**Status:** Accepted (Phase 0)

## Context

Web research needs a search backend for v1; must remain provider-neutral.

## Decision

Implement `WebSearchProvider` protocol; `TavilySearchAdapter` as first concrete adapter.

## Consequences

- Tavily API key required for live web research in dev
- Future adapters (Brave, SerpAPI, MCP) plug in without workflow changes
