# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 3 research orchestrator: outer loop (`ResearchOrchestrator`), structured planner, deterministic termination, budget gate
- Tavily `WebSearchProvider` adapter with normalized `SearchResult` boundary (search candidates ≠ sources ≠ snapshots)
- Secure fetch foundation (SSRF policy: scheme allowlist, DNS/IP checks, redirect limits)
- Typed research run events for SSE foundation; LangSmith phase tracing on orchestrator/planner
- `POST /api/v1/research-runs/{id}/execute` background execution (202 Accepted)
- Alembic migration `002`: `search_candidates`, contradiction `evidence_status`
- Phase 2 hardening: snapshot immutability tests, cross-run guards, contradiction invariants, question lifecycle, atomic budget ledger
- `docs/architecture/AGENT_ENGINEERING.md` (2026 agent engineering matrix)
- Research/security tests: termination, Tavily contract, secure fetch, orchestrator integration, context boundary

### Changed

- Budget semantics: `is_exhausted` when at limit; `would_exceed` blocks overrun without rejecting final allowed unit
- `add_source` returns `(row, created)` tuple for idempotent dedupe signaling
- Contradiction writes require `evidence_status`; duplicate A↔B pairs are idempotent

### Added (Phase 2)
- PostgreSQL persistence layer with SQLAlchemy models, Alembic migration `001`, and focused `ResearchStore`
- Minimal research run API: `POST/GET /api/v1/research-runs`
- Postgres-backed tests for domain invariants, store operations, migrations, and API validation
- pgvector extension bootstrap in initial migration (vector tables deferred to Phase 5)

### Changed

- Google default chat model updated to `gemini-3.7-flash` (GA verified 2026-08-20)
- Google default embedding model updated to `gemini-embedding-2`
- Provider factory uses provider-neutral `ModelBuildOptions` (timeout, max_retries) instead of universal `temperature`
- Smoke agent reports resolved runtime model ID from the LangChain chat model instance
- LangSmith observability supports optional `LANGSMITH_WORKSPACE_ID` and `LANGSMITH_ENDPOINT`
- API version bumped to `0.2.0`
- CI runs PostgreSQL service, applies Alembic migrations, and executes non-integration pytest suite

### Added (Phase 1.1)

- Provider contract tests for Google, OpenAI, and Anthropic factory kwargs
- Optional live Google runtime + LangSmith integration tests (require local `.env`)

- Monorepo scaffold: `apps/api`, `apps/web`, `libs/core`, `libs/providers`, `libs/research`
- Multi-provider LLM factory (Google, OpenAI, Anthropic)
- LangChain `create_agent` smoke path (`/api/v1/smoke/agent`)
- FastAPI health and dependency checks
- Next.js frontend shell
- Docker Compose (PostgreSQL/pgvector, Redis, API, web)
- Public CI: hygiene scan, ruff, pytest, frontend build
- Python tests for defaults, factory, API, smoke agent

### Changed

- Public CI uses generic repository hygiene checks only (no private tooling references)

### Phase 0.5 (included in repository baseline)

- Apache-2.0 license, architecture docs, ADRs, threat model, contributor governance
