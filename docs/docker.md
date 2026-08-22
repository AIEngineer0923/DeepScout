# Docker

Local and containerized deployment using files in `infra/docker/`.

## Compose stack (development)

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

| Service | Image | Host port | Purpose |
|---------|-------|-----------|---------|
| `postgres` | `pgvector/pgvector:pg16` | `127.0.0.1:5432` | Primary database |
| `redis` | `redis:7-alpine` | `127.0.0.1:6379` | Cache / optional queue |
| `api` | built from `Dockerfile.api` | `127.0.0.1:8000` | FastAPI |
| `web` | built from `Dockerfile.web` | `127.0.0.1:3000` | Next.js |

Compose uses a **lab-only** Postgres password (`deepscout`/`deepscout`). Do not expose these ports publicly without changing credentials.

### Migrations inside compose

After Postgres is healthy:

```bash
cd libs/persistence
DATABASE_URL=postgresql+psycopg://deepscout:deepscout@127.0.0.1:5432/deepscout uv run alembic upgrade head
```

Or exec into the `api` container if you run the full stack.

## API image

`infra/docker/Dockerfile.api`:

- Multi-stage build with `uv sync --all-packages`
- Exposes port 8000
- Healthcheck: `GET /health`
- Entrypoint: `infra/docker/entrypoint.sh`
  - `DEEPSCOUT_PROCESS_ROLE=worker` → `python -m deepscout_research.jobs.worker`
  - default → `deepscout-api`

Used by Railway for production API and worker services.

## Web image

`infra/docker/Dockerfile.web`:

- Next.js `standalone` output
- Exposes port 3000

Production frontend is usually deployed on Vercel instead of this image.

## Environment

Pass env via `.env` file referenced in compose or `-e` flags. Required for research:

- `DATABASE_URL`
- LLM + Tavily keys

See [configuration.md](configuration.md).

## Health checks

| Endpoint | Meaning |
|----------|---------|
| `GET /health` | Process alive |
| `GET /ready` | Postgres reachable; hosted also checks schema revision + `evaluation_results` |

## Production differences

- Bind `API_HOST=0.0.0.0`, set `PORT` from platform
- Use managed Postgres with TLS (`sslmode=require`)
- Separate migration admin role from app role
- Do not publish Postgres/Redis to the public internet

Full deployment: [DEPLOYMENT.md](DEPLOYMENT.md).
