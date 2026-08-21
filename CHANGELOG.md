# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- ADR-010 production resilience: capability registry, optional capability/privacy-gated fallback, error taxonomy, in-process provider health, `/live`+`/ready`, engine dispose on shutdown
- `invoke_with_resilience` helper with application-owned retry ownership; approval spoofing guards (HITL product pause still deferred)
- Phase 5 hybrid retrieval: pgvector + PostgreSQL FTS, RRF fusion, deterministic rerank, run-scoped indexing pipeline
- Document chunks and embedding records derived from immutable `SourceSnapshot` rows with versioning metadata
- Structured retrieval planner, strategy policy, retrieval grader, and bounded re-retrieval
- `scripts/deepscout_index.py` backfill command; ADR-008; RAG technique landscape review; RAG threat model T20–T24
- Retrieval evaluators (Recall@K, MRR, Hit@K, NDCG@K, cross-run isolation) and optional RAGAS offline wrapper
- Phase 5 closure gate (`scripts/phase5_closure_gate.py`): symmetric 768-vs-1536, isolated pre-RAG vs RAG, category ablation, LangSmith live experiments
- Default Google embedding dimensions set to **768** after measured parity with 1536 on retrieval-benchmark-v1.1
- Optional run-scoped compiled knowledge layer (ADR-009): WikiPage/WikiStatement with claim→evidence provenance, deterministic compiler, Obsidian Markdown export, Graphify rejected for DeepScout runtime

### Changed

- `LLM_TIMEOUT_S` / `LLM_MAX_RETRIES` now wire into LangChain model build options via `options_from_settings`
- Dependency health reports `redis_required=false` (Redis remains optional MODE A probe)

### Security

- Document MODE A (local/trusted network) as the supported deployment; public Internet auth is not implemented
- LangSmith tracing defaults to off; research content is opt-in for remote traces
- Reuse a pooled SQLAlchemy engine per database URL; dispose health-check engines and Redis clients
- Cap in-process rate-limit keys; reject oversized request bodies after read; `Cache-Control: no-store` on API responses
- Duplicate execute/resume reuses an active job; source insert races return the existing row
- Compose publishes ports on `127.0.0.1`; container healthchecks; expanded `.dockerignore`; API image OS packages upgraded; web runtime drops unused npm CLI
- Pre-Phase-5 security gate: dependency upgrades (Next 15.5.23, Vitest 3.2.6, PostCSS 8.5.23, sharp 0.35.3), CodeQL, Semgrep, pip-audit, npm audit
- Secure fetch now pins TCP connect to the DNS-checked IP
- CSV formula-injection sanitization, security headers, optional IP rate limits
- Smoke agent disabled by default; API docs disabled; default bind 127.0.0.1
- Worker tool allowlists clamp unknown tools; search URLs are filtered before persistence
- Model/retrieved text cannot spoof human approval; malicious provider-style strings cannot alter routing policy

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

- Reapplied pre-RAG visual fidelity (layout tokens, topology, drawers, Playwright baselines) onto current main without reverting security, CSP, or API contracts
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
