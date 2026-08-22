# Troubleshooting

## Local development

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `connection refused` to database | Postgres not running | `docker compose -f infra/docker/docker-compose.yml up -d` |
| Alembic fails | Wrong cwd or DB down | Run from `libs/persistence`; check `DATABASE_URL` |
| Research fails immediately | Missing API keys | Set `GOOGLE_API_KEY` and `TAVILY_API_KEY` in `.env` |
| CORS error in browser | Origin not allowed | Add `http://localhost:3000` to `CORS_ORIGINS` |
| `/ready` 503 (hosted) | Missing OAuth secrets or schema | Check `SESSION_SECRET`, `CREDENTIAL_ENCRYPTION_KEY`, migrations at head |
| Worker idle, run stuck | Worker not running | Start `DEEPSCOUT_PROCESS_ROLE=worker uv run python -m deepscout_research.jobs.worker` |
| Playwright visual tests fail | No local baselines | Run `npx playwright test e2e/visual.spec.ts --update-snapshots` or skip (CI skips them) |

## Self-hosting

| Symptom | Check |
|---------|-------|
| API 502 from Vercel | `API_REWRITE_ORIGIN` points to live Railway API |
| SSE stalls | `DATABASE_LISTEN_URL` direct connection (not transaction pooler) for NOTIFY |
| Migrations fail on app role | Use admin role for `alembic upgrade`; app role for runtime only |
| OAuth redirect mismatch | Callback URLs match `PUBLIC_BASE_URL` |

## Research quality

| Symptom | Notes |
|---------|-------|
| Many evaluators "Unavailable" | Expected for offline/ground-truth metrics — not a bug |
| Empty report | Check run status, budget exhaustion, critic failure in events |
| No sources | Tavily key, budget `max_sources`, fetch errors in run events |

## Getting help

- Bugs: GitHub Issues (non-security)
- Security: [SECURITY.md](../SECURITY.md) private advisories
