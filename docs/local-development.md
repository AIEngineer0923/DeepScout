# Local development

Get DeepScout running on your machine in MODE A (no login).

## Prerequisites

| Tool | Version |
|------|---------|
| Git | any recent |
| Docker | for Postgres + Redis |
| Python | 3.12+ |
| Node.js | 20 LTS |
| [uv](https://docs.astral.sh/uv/) | Python package manager |

## Clone and install

```bash
git clone https://github.com/francescoveryra-dot/deepscout.git
cd deepscout
cp .env.example .env
```

Edit `.env` — minimum for a research run:

- `GOOGLE_API_KEY` (or another supported LLM provider)
- `TAVILY_API_KEY` (web search)

Never commit `.env`.

```bash
uv sync --all-packages --dev
cd apps/web && npm ci && cd ../..
```

## Database and migrations

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

This starts Postgres (pgvector) and Redis on `127.0.0.1` only.

```bash
cd libs/persistence
uv run alembic upgrade head
cd ../..
```

Confirm: `uv run alembic current` should show head (e.g. `012`).

## Run the stack

Terminal 1 — API (binds `127.0.0.1:8000` by default):

```bash
uv run deepscout-api
```

Terminal 2 — frontend:

```bash
cd apps/web
npm run dev
```

Open http://localhost:3000. API OpenAPI: http://127.0.0.1:8000/docs

## Optional: worker

For background job execution (closer to production):

```bash
DEEPSCOUT_PROCESS_ROLE=worker uv run python -m deepscout_research.jobs.worker
```

MODE A can also execute runs synchronously via API in some paths; the worker is required for hosted-style job queues.

## Tests

```bash
# Secret scan (required before push)
bash scripts/scan-secrets.sh

# Python (matches CI)
uv run ruff check .
uv run pytest -m "not integration"

# Frontend
cd apps/web
npm test
npm run build
```

Integration tests need Postgres: `uv run pytest -m integration`

Playwright E2E (local):

```bash
cd apps/web
npx playwright install chromium
npm run test:e2e
```

Visual regression baselines are **local-only** (gitignored). Regenerate with:

```bash
npx playwright test e2e/visual.spec.ts --update-snapshots
```

## Docker-only path

See [docker.md](docker.md) for building and running API + web containers.

## Troubleshooting

| Problem | Check |
|---------|--------|
| `connection refused` to DB | `docker compose -f infra/docker/docker-compose.yml ps`; `DATABASE_URL` in `.env` |
| Alembic errors | Run from `libs/persistence`; DB must be up |
| Research fails immediately | Provider keys in `.env`; Tavily quota |
| CORS errors | `CORS_ORIGINS` includes `http://localhost:3000` |
| Port in use | Change `API_PORT` or Next.js port |

## Hosted mode locally

To test MODE B you need OAuth apps, `SESSION_SECRET`, `CREDENTIAL_ENCRYPTION_KEY`, and `DEEPSCOUT_DEPLOYMENT_MODE=hosted`. See [DEPLOYMENT.md](DEPLOYMENT.md) and [configuration.md](configuration.md).

## Next steps

- [configuration.md](configuration.md) — all environment variables
- [providers.md](providers.md) — API keys and BYOK
- [DEPLOYMENT.md](DEPLOYMENT.md) — production/self-host
