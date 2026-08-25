# Docker

DeepScout has two container paths with different purposes:

- **development from source** builds the current checkout;
- **self-hosting from a release** pulls immutable public images from GHCR.

Both paths run in MODE A by default. MODE A has no authentication and must stay on a trusted
machine or private network.

## Prerequisites

- Docker Engine or Docker Desktop with Compose v2
- Git for checking out the matching release configuration
- A copied `.env.example` file; provider keys are only needed to execute research

## Self-host from released images

Check out the release whose compose file you intend to run:

```bash
git clone --branch v0.1.5 --depth 1 https://github.com/francescoveryra-dot/deepscout.git
cd deepscout
cp .env.example .env
```

The default v0.1.5 images are:

```text
ghcr.io/francescoveryra-dot/deepscout-api:0.1.5
ghcr.io/francescoveryra-dot/deepscout-web:0.1.5
```

They are public and support `linux/amd64` and `linux/arm64`. The API image is deliberately reused
for three process roles: one-shot database migration, FastAPI, and the research worker. Publishing a
separate worker image would duplicate the same filesystem and dependency graph.

Pull and start the stack:

```bash
docker compose -f infra/docker/docker-compose.release.yml pull
docker compose -f infra/docker/docker-compose.release.yml up -d
docker compose -f infra/docker/docker-compose.release.yml ps
```

The `migrate` service applies Alembic head `017` and exits successfully before the API and worker
start. PostgreSQL/pgvector and Redis run as separate services. The web image sends same-origin API
requests through its built-in rewrite to the Compose service `api:8000`.

Verify a no-provider-key installation:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:3000
docker compose -f infra/docker/docker-compose.release.yml logs migrate
```

Open <http://localhost:3000>. Research execution remains unavailable until `.env` contains a
supported model-provider key and `TAVILY_API_KEY`. No maintainer credentials are present in the
images.

Stop the stack without deleting its database volume:

```bash
docker compose -f infra/docker/docker-compose.release.yml down
```

Use `down --volumes` only when you intentionally want to erase the local database.

### Pin or override an image

The compose file defaults to the exact release version. Advanced users can point at an immutable
SHA tag or an internal mirror without editing the file:

```bash
export DEEPSCOUT_API_IMAGE=ghcr.io/francescoveryra-dot/deepscout-api:sha-<short-sha>
export DEEPSCOUT_WEB_IMAGE=ghcr.io/francescoveryra-dot/deepscout-web:sha-<short-sha>
docker compose -f infra/docker/docker-compose.release.yml pull
```

`latest` follows the newest published GitHub Release. Production operators should prefer an exact
version or digest.

## Develop from source

```bash
cp .env.example .env
docker compose -f infra/docker/docker-compose.yml up -d --build
```

| Service | Image | Host port | Purpose |
|---------|-------|-----------|---------|
| `postgres` | `pgvector/pgvector:pg16` | `127.0.0.1:5432` | Primary database |
| `redis` | `redis:7-alpine` | `127.0.0.1:6379` | Optional cache/wake channel |
| `api` | built from `Dockerfile.api` | `127.0.0.1:8000` | FastAPI |
| `web` | built from `Dockerfile.web` | `127.0.0.1:3000` | Next.js |

Apply migrations from the host after Postgres is healthy:

```bash
cd libs/persistence
DATABASE_URL=postgresql+psycopg://deepscout:deepscout@127.0.0.1:5432/deepscout \
  uv run alembic upgrade head
```

Run the worker from source when testing background execution:

```bash
DEEPSCOUT_PROCESS_ROLE=worker uv run python -m deepscout_research.jobs.worker
```

## Image roles and health

`infra/docker/Dockerfile.api` installs the locked production Python workspace and runs as the
non-root `deepscout` user:

| `DEEPSCOUT_PROCESS_ROLE` | Process |
|--------------------------|---------|
| `api` or unset | `deepscout-api` |
| `worker` | `deepscout_research.jobs.worker` |
| `migrate` | `deepscout-migrate` → Alembic head |

`infra/docker/Dockerfile.web` builds Next.js standalone output and also runs as `deepscout`.

| Endpoint | Meaning |
|----------|---------|
| `GET /health` or `/live` | API process is alive |
| `GET /ready` | PostgreSQL reachable; hosted mode also checks schema and auth configuration |

## Runtime configuration and security

- `.dockerignore` excludes `.env*`, `.git`, virtual environments, Node modules, build output,
  tests, local transcripts, and editor state.
- Both application images run as an unprivileged user.
- The API image uses a pinned Alpine base; release Compose drops all application
  capabilities, enables `no-new-privileges`, uses read-only roots, and provides bounded tmpfs mounts.
- Provider, OAuth, database, Railway, Vercel, and Supabase credentials are runtime configuration;
  none are build arguments or image content.
- Production containers use `uv.lock` and `package-lock.json`.
- Release manifests include OCI source/version/revision/license labels, SBOM and BuildKit
  provenance, GitHub artifact attestations, and a blocking HIGH/CRITICAL vulnerability scan.
- Local compose ports bind to `127.0.0.1`. Do not publish MODE A directly to the Internet.

For hosted OAuth/BYOK requirements and generic infrastructure topology, see
[DEPLOYMENT.md](DEPLOYMENT.md). For all variables, see [configuration.md](configuration.md).
