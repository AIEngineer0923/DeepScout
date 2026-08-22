# Configuration

Environment variables for DeepScout. Copy [.env.example](../.env.example) and fill values locally. **Never commit real secrets.**

## Deployment mode

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSCOUT_DEPLOYMENT_MODE` | `local` | `local` (MODE A) or `hosted` (MODE B) |

MODE B requires `SESSION_SECRET`, `CREDENTIAL_ENCRYPTION_KEY`, and OAuth client IDs/secrets or the API fails closed on `/ready`.

## Database

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+psycopg://...` SQLAlchemy URL |
| `DATABASE_LISTEN_URL` | Hosted + pooler | Direct connection for `LISTEN/NOTIFY` if `DATABASE_URL` uses a transaction pooler |

Local compose default is in `.env.example` (lab password only).

## API / process

| Variable | Default | Description |
|----------|----------|-------------|
| `API_HOST` | `127.0.0.1` | Bind address |
| `API_PORT` | `8000` | HTTP port |
| `DEEPSCOUT_PROCESS_ROLE` | `api` | `api` or `worker` |
| `CORS_ORIGINS` | localhost | Comma-separated origins |
| `PUBLIC_BASE_URL` | — | Hosted: canonical web URL for OAuth redirects |

## LLM providers (MODE A or maintainer)

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Gemini |
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `LLM_PROVIDER` / per-run overrides | Factory default |

## Search

| Variable | Description |
|----------|-------------|
| `TAVILY_API_KEY` | Web search v1 adapter |

## Hosted auth (MODE B)

| Variable | Description |
|----------|-------------|
| `SESSION_SECRET` | Session signing secret |
| `CREDENTIAL_ENCRYPTION_KEY` | 32-byte key (raw or urlsafe base64) for BYOK vault |
| `GITHUB_OAUTH_CLIENT_ID` / `SECRET` | GitHub OAuth |
| `GOOGLE_OAUTH_CLIENT_ID` / `SECRET` | Google OAuth |

## Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | local compose | Optional in hosted prod; used for probes in MODE A |

## Research defaults

See `.env.example` for budget limits: `RESEARCH_MAX_ITERATIONS`, `RESEARCH_MAX_COST_USD`, etc.

## Retrieval

| Variable | Default | Description |
|----------|---------|-------------|
| `RETRIEVAL_MODE` | `hybrid` | `lexical`, `dense`, or `hybrid` |

## LangSmith (optional)

| Variable | Description |
|----------|-------------|
| `LANGSMITH_API_KEY` | Tracing API key |
| `LANGSMITH_TRACING` | `true`/`false` |
| `LANGSMITH_PROJECT` | Project name |

Hosted users control tracing via account settings; maintainer keys are not used for user runs.

## Frontend (Vercel)

| Variable | Description |
|----------|-------------|
| `API_REWRITE_ORIGIN` | Production: backend origin for Next.js rewrites |
| `NEXT_PUBLIC_API_URL` | Usually unset in prod (same-origin `/api`) |

Server-only secrets must **not** be set on Vercel.

## Migration role vs app role

Production Postgres should use:

- **Admin/migration role** — `alembic upgrade head` only
- **Application role** — `deepscout_app` with DML on app tables, no DDL

The app never embeds admin credentials.

See [providers.md](providers.md) for how user API keys are stored on hosted instances.
