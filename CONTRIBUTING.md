# Contributing to DeepScout

Thanks for contributing. This is a real monorepo — keep changes focused and tested.

## Prerequisites

- Git
- Docker (Postgres + Redis for local dev)
- Python 3.12+
- Node.js 20 LTS
- [uv](https://docs.astral.sh/uv/) for Python

## Setup

See [docs/local-development.md](docs/local-development.md).

```bash
git clone https://github.com/francescoveryra-dot/deepscout.git
cd deepscout
cp .env.example .env
uv sync --all-packages --dev
docker compose -f infra/docker/docker-compose.yml up -d
cd libs/persistence && uv run alembic upgrade head && cd ../..
```

## Workflow

1. Fork or branch from `main`
2. One logical change per PR
3. Run quality gates locally (below)
4. `bash scripts/scan-secrets.sh` before every push
5. Open a PR with description and test plan

Do not push directly to `main`.

## Quality gates (match CI)

```bash
uv run ruff check .
uv run pytest -m "not integration"
cd apps/web && npm ci && npm test && npm run build
bash scripts/scan-secrets.sh
```

Optional locally: `uv run --with semgrep semgrep scan --config .semgrep.yml --error --quiet`

## Conventions

- Match existing style in each module (Ruff enforces Python)
- Minimal diffs — no drive-by refactors
- No secrets in code, logs, tests, or docs
- No fake evaluator PASS or placeholder features presented as complete
- Architecture changes: update relevant doc in `docs/` (see [AGENTS.md](AGENTS.md))

## Migrations

Schema changes require Alembic revisions under `libs/persistence/alembic/versions/`. Never edit applied production migrations in place.

## Screenshots and assets

- Product screenshots live in `docs/assets/screenshots/`
- Do **not** commit Playwright visual baselines (`apps/web/e2e/**/*.spec.ts-snapshots/`)
- Do **not** commit `test-results/`, `playwright-report/`, or `.env`

## Documentation

When you change behavior, update the matching doc:

| Area | Doc |
|------|-----|
| Agent runtime | `docs/agent-runtime.md` |
| Evaluations | `docs/evaluations.md` |
| Deployment | `docs/DEPLOYMENT.md` |
| Env vars | `.env.example`, `docs/configuration.md` |

## Security

Report vulnerabilities via [GitHub private security advisories](https://github.com/francescoveryra-dot/deepscout/security/advisories) — not public issues. See [SECURITY.md](SECURITY.md).

## License

Contributions are licensed under Apache License 2.0.
