# DeepScout — Environment

Contributor reference. For setup steps see [local-development.md](local-development.md).

## Repository

- Remote: `https://github.com/francescoveryra-dot/deepscout.git`
- Default branch: `main`
- Version: **0.1.0** (see root `pyproject.toml`)

## Stack

| Component | Version |
|-----------|---------|
| Python | 3.12+ |
| Node.js | 20 LTS |
| PostgreSQL | 16+ with pgvector |
| Redis | 7+ (optional in hosted prod) |
| Docker | current stable |

## Monorepo layout

| Path | Role |
|------|------|
| `apps/api/` | FastAPI backend |
| `apps/web/` | Next.js frontend |
| `libs/core/` | Settings, domain schemas |
| `libs/research/` | Orchestrator, phases, retrieval, worker |
| `libs/persistence/` | SQLAlchemy, Alembic |
| `libs/evaluation/` | Evaluator registry and persistence |
| `libs/providers/` | LLM/embedding factory |
| `infra/docker/` | Docker Compose |
| `docs/` | Documentation |
| `scripts/` | Tooling (secret scan, backfill, benchmarks) |

## Commands

```bash
# Secret scan (required before push)
bash scripts/scan-secrets.sh

# Python tests (CI subset)
uv run pytest -m "not integration"

# Full Python + lint
uv run ruff check .
uv run pytest -m "not integration"

# Frontend
cd apps/web && npm test && npm run build

# Docker stack
docker compose -f infra/docker/docker-compose.yml up -d

# Migrations
cd libs/persistence && uv run alembic upgrade head
```

## CI

GitHub Actions: `.github/workflows/ci.yml` (validate, Python, web) and `codeql.yml`.

External contributors do not need private maintainer tooling.

## Production modes

| Mode | Env value | Notes |
|------|-----------|-------|
| Local (MODE A) | `DEEPSCOUT_DEPLOYMENT_MODE=local` | No login; keys in `.env` |
| Hosted (MODE B) | `hosted` | OAuth + BYOK |

See [DEPLOYMENT.md](DEPLOYMENT.md).
