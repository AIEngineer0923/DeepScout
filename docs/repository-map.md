# Repository map

Physical layout of the DeepScout monorepo. Paths are from the repository root.

## Applications

| Path | Package | Entry / notes |
|------|---------|----------------|
| `apps/web/` | `deepscout-web` | Next.js 15 App Router; `src/app/` pages; `npm run dev` |
| `apps/api/` | `deepscout-api` | FastAPI; `deepscout_api/app.py`; CLI `uv run deepscout-api` |

## Libraries (`libs/`)

| Path | Responsibility |
|------|----------------|
| `libs/core/` | Settings (`deepscout_core/settings.py`), domain enums/schemas, deployment mode |
| `libs/providers/` | LangChain LLM + embedding factory |
| `libs/research/` | Orchestrator, phases, planner, retrieval, fetch, demos, worker, HITL |
| `libs/persistence/` | SQLAlchemy models, `ResearchStore`, Alembic, retrieval SQL |
| `libs/evaluation/` | Evaluator registry, deterministic runners, persist/load |

Retrieval and secure fetch are **inside** `libs/research` and `libs/persistence`, not separate top-level packages.

## Research subsystem (`libs/research/src/deepscout_research/`)

| Directory | Purpose |
|-----------|---------|
| `orchestrator.py` | Main state machine |
| `planner.py` | Semantic research planner |
| `phases/` | Per-phase agents (plan, research, extract, report, …) |
| `retrieval/` | `RetrievalService`, fusion, query planner |
| `fetch/` | SSRF-safe HTTP fetch |
| `tasks/` | Task graph validation |
| `demo/` | Public demo catalog and publication |
| `credentials/` | BYOK vault integration |
| `hitl/` | Human-in-the-loop reviews |
| `jobs/worker.py` | Background job runner |

## Persistence

| Path | Purpose |
|------|---------|
| `libs/persistence/src/deepscout_persistence/models.py` | ORM models |
| `libs/persistence/src/deepscout_persistence/store.py` | `ResearchStore` API |
| `libs/persistence/alembic/versions/` | Migrations (`012` = `evaluation_results`) |

## Frontend routes (`apps/web/src/app/`)

| Route | Screen |
|-------|--------|
| `/dashboard` | Overview |
| `/research/new` | New research |
| `/research/[runId]` | Live research |
| `/research/[runId]/plan` | Plan / DAG |
| `/research/[runId]/workers` | Research agents |
| `/research/[runId]/sources` | Sources |
| `/research/[runId]/snapshots` | Captured content |
| `/research/[runId]/claims` | Claims / evidence |
| `/research/[runId]/quality` | Quality / contradictions |
| `/research/[runId]/report` | Final report |
| `/research/[runId]/evaluations` | Evaluations |
| `/demo` | Explore demo |

## Tests

| Path | Scope |
|------|-------|
| `tests/research/` | Orchestrator, phases, HITL, runtime |
| `tests/security/` | Tenant isolation, injection, demo mutations |
| `tests/persistence/` | Store, retrieval SQL |
| `tests/evaluation/` | Matrix, persist, registry |
| `tests/demo/` | Demo publication |
| `apps/web/e2e/` | Playwright (product, security, visual) |

## Operations

| Path | Purpose |
|------|---------|
| `infra/docker/` | Dockerfiles, `docker-compose.yml` |
| `scripts/` | Secret scan, demo publish, benchmarks, backfill |
| `docs/` | Human documentation |
| `.github/workflows/` | CI, CodeQL |
| `railway.toml` | Railway API image build |
| `apps/web/vercel.json` | Vercel build settings |

## Configuration

| File | Purpose |
|------|---------|
| `.env.example` | Documented env template (no secrets) |
| `pyproject.toml` | uv workspace root |
| `apps/web/package.json` | Frontend deps |
| `.semgrep.yml` | SAST rules |

For coding agents, see [AGENTS.md](../AGENTS.md).
