# DeepScout

**Autonomous Research & Decision Intelligence** — open-source agentic research system.

DeepScout receives a complex research objective, builds a bounded research plan,
collects sources, extracts claims and evidence, detects contradictions, iterates when
evidence is insufficient, runs a critic pass, and produces a documented decision or
synthesis with provenance and confidence.

This is **not** a chatbot or a simple RAG demo.

## Status

| Phase | State |
|---|---|
| Phase 0 | Architecture approved |
| Phase 0.5 | Public repository baseline |
| Phase 1 | Monorepo scaffold, provider factory, smoke agent |

## Architecture at a glance

```text
User Goal
  → Orchestrator (bounded state machine)
    → LangChain agents per phase
      → Tools (web search, fetch, retrieval)
        → Evidence graph (PostgreSQL + pgvector)
          → Report + Decision
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full picture.

## Stack

- **Frontend:** Next.js, React, TypeScript
- **API:** FastAPI, Server-Sent Events
- **Agents:** LangChain Python
- **Database:** PostgreSQL + pgvector
- **Cache:** Redis
- **Observability:** LangSmith
- **LLM providers:** Google Gemini, OpenAI, Anthropic
- **Web search v1:** Tavily (pluggable adapter)

## Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture |
| [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md) | Project identity |
| [docs/architecture/](docs/architecture/) | Detailed design |
| [docs/threat-model/THREAT_MODEL.md](docs/threat-model/THREAT_MODEL.md) | Security threat model |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guide |
| [SECURITY.md](SECURITY.md) | Security policy |

## Quick start

```bash
git clone git@github.com:francescoveryra-dot/deepscout.git
cd deepscout
cp .env.example .env
# Add API keys locally — never commit .env

# Python (from repo root)
uv sync --all-packages --dev
uv run pytest

# Infrastructure
docker compose -f infra/docker/docker-compose.yml up -d

# API
uv run deepscout-api

# Web (separate terminal)
cd apps/web && npm ci && npm run dev
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Author

Francesco Iaforte — [github.com/francescoveryra-dot](https://github.com/francescoveryra-dot)
