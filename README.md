# Deep Scout

**Autonomous Research & Decision Intelligence** — open-source agentic research system.

## Live Demo / Run Locally / Deploy Your Own

| Path | What you get |
|---|---|
| **Explore Demo** | `/demo` — read-only published runs, no signup, zero provider spend |
| **Run locally (MODE A)** | Clone, `.env` provider keys, no account |
| **Hosted (MODE B)** | GitHub/Google login, BYOK vault, tenant isolation |
| **Deploy your own** | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — generic OAuth/DB/keys, no personal-account hardcoding |

One-click Vercel is not offered: the agent runtime needs a persistent FastAPI worker.

See [docs/adr/011-mode-b-hosted.md](docs/adr/011-mode-b-hosted.md).

This is **not** a chatbot, a SaaS billing product, or a simple RAG demo.

## Status

| Phase | State |
|---|---|
| Phase 0 | Architecture approved |
| Phase 0.5 | Public repository baseline |
| Phase 1 | Monorepo scaffold, provider factory, smoke agent |
| Product runtime | Planner, follow-up, PIN/EXCLUDE, monitors, RUM |
| Mode B | Hosted auth, tenancy, BYOK, public demo |

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
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Local/trusted deployment (MODE A) |
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
