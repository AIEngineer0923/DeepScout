# DeepScout — Environment

Development environment reference for contributors and maintainers.

## Repository

- Name: DeepScout
- Remote: `git@github.com:francescoveryra-dot/deepscout.git`
- Branch: `main`

## Git identity (maintainer)

- Name: `Francesco Iaforte`
- Email: `255975034+francescoveryra-dot@users.noreply.github.com`

## Local setup

```bash
git clone git@github.com:francescoveryra-dot/deepscout.git
cd deepscout
cp .env.example .env
# Fill .env locally — never commit it
```

## Stack (target)

| Component | Version policy |
|---|---|
| Python | 3.12+ |
| Node.js | 20 LTS+ (Phase 1+) |
| PostgreSQL | 16+ with pgvector |
| Redis | 7+ |
| Docker | current stable |

## Environment variables

See [.env.example](../.env.example). Required for full functionality (Phase 1+):

- LLM provider keys (`GOOGLE_API_KEY` minimum for initial dev)
- `TAVILY_API_KEY` for web search adapter
- `LANGSMITH_API_KEY` for tracing (optional in CI)
- `DATABASE_URL`, `REDIS_URL`

LangSmith project `deepscout-dev` is created automatically on first trace when
`LANGSMITH_PROJECT=deepscout-dev` is set.

## Monorepo paths (Phase 1+)

| Path | Role |
|---|---|
| `apps/api/` | FastAPI backend |
| `apps/web/` | Next.js frontend |
| `libs/` | Python packages |
| `infra/docker/` | Docker Compose |
| `docs/` | Architecture and operations |
| `scripts/` | Repository tooling |

## Development commands

```bash
# Secret scan (required before push)
bash scripts/scan-secrets.sh

# Phase 1+ (not yet available)
# docker compose -f infra/docker/docker-compose.yml up -d
# pytest
# npm test --prefix apps/web
```

## CI

Public CI runs on GitHub Actions (`.github/workflows/ci.yml`).

External contributors do **not** need any private tooling to clone, test, or contribute.

## Production

Supported production-like use is **MODE A** (local or trusted network). See
[DEPLOYMENT.md](DEPLOYMENT.md). Public Internet with first-party auth is not
implemented (Phase 10+).

`CONTROLLED_AUTO_DEPLOY=disabled_until_configured` until runtime map and rollback
are defined.

## Related docs

- [PROJECT_SPEC.md](PROJECT_SPEC.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)
- [threat-model/THREAT_MODEL.md](threat-model/THREAT_MODEL.md)
