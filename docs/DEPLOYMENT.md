# DeepScout deployment

## Three product modes

| Mode | Env | Auth | Credentials | Audience |
|---|---|---|---|---|
| **A — local / self-host** | `DEEPSCOUT_DEPLOYMENT_MODE=local` (default) | None | `GOOGLE_API_KEY`, `TAVILY_API_KEY`, … | Operator laptop |
| **B — hosted authenticated** | `hosted` | GitHub + Google OAuth | User vault only | Signed-in researchers |
| **Public demo** | either | None | None | Recruiters / visitors |

Hosted + missing `SESSION_SECRET`, `CREDENTIAL_ENCRYPTION_KEY`, or OAuth clients fails closed.
It never silently becomes MODE A.

## MODE A — run locally

1. Clone, copy `.env.example`, set provider keys.
2. Start Postgres with pgvector (`infra/docker/docker-compose.yml`).
3. `uv run alembic upgrade head` from `libs/persistence`.
4. API: `uv run deepscout-api` (default bind `127.0.0.1`).
5. Web: `npm run dev` in `apps/web`.

Do not bind `0.0.0.0` unless you understand that MODE A has no login.

## MODE B — self-host hosted mode

Another operator configures **their** OAuth apps, database, session secret, and encryption key.
Nothing is hardcoded to a personal Vercel or Railway account.

Required:

```
DEEPSCOUT_DEPLOYMENT_MODE=hosted
SESSION_SECRET=                    # long random
CREDENTIAL_ENCRYPTION_KEY=         # 32 raw bytes or urlsafe base64 of 32 bytes
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
PUBLIC_BASE_URL=https://your-web.example
CORS_ORIGINS=https://your-web.example
DATABASE_URL=postgresql+psycopg://...
DATABASE_LISTEN_URL=postgresql+psycopg://...   # required if DATABASE_URL is a transaction pooler
```

OAuth callback URLs (same-origin via the frontend reverse-proxy is preferred):

- `{PUBLIC_BASE_URL}/api/v1/auth/callback/github`
- `{PUBLIC_BASE_URL}/api/v1/auth/callback/google`

Hosted users paste their own Gemini/OpenAI/Anthropic/Tavily keys. Maintainer env keys are never used
for user research.

## Production hosting split (this repository's public deployment)

| Piece | Host | Why |
|---|---|---|
| Next.js | Vercel | Static/SSR frontend, CDN, preview deploys |
| FastAPI + worker | Persistent Docker host (Railway in the public deployment) | Long research, SSE, LISTEN/NOTIFY, durable jobs, scheduler tick |
| PostgreSQL + pgvector | Managed Postgres (Supabase in the public deployment) | Authoritative state, SKIP LOCKED, LISTEN |

This is **two platforms plus a database**, not one-click. Do not put the agent runtime on Vercel Functions.

Suggested process topology:

- `api` — `DEEPSCOUT_PROCESS_ROLE=api` (uvicorn, `API_HOST=0.0.0.0`, `PORT` from the platform)
- `worker` — `DEEPSCOUT_PROCESS_ROLE=worker` (existing `run_worker`, includes monitor dispatch)
- no extra scheduler service

Migrations run **once** per release (`uv run alembic upgrade head` from `libs/persistence`), not on every worker.

Disable idle sleep / keep a minimum replica. Transaction poolers must not be used for LISTEN.

## Vercel

The Next.js app can be deployed to Vercel. Set production-only:

- `API_REWRITE_ORIGIN` — persistent API origin (server rewrite for `/api`, `/live`, `/ready`, `/health`)
- leave `NEXT_PUBLIC_API_URL` unset in production so the browser uses same-origin `/api`

Do not put production OAuth secrets, `SESSION_SECRET`, `CREDENTIAL_ENCRYPTION_KEY`, or `DATABASE_URL` on Vercel. Those belong on the persistent API/worker.

Preview deployments from untrusted forks must not receive production secrets.

One-click Vercel is not offered: it would imply a working agent runtime that Vercel cannot host.

## Public Internet

MODE A on a public bind is unsafe. MODE B is the public-Internet architecture, plus a persistent worker.
