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
| `RATE_LIMIT_ENABLED` | `false` | Required for Internet-facing MODE B |
| `RATE_LIMIT_MAX_REQUESTS` | `120` | Per-client requests in each window |
| `RATE_LIMIT_MUTATING_MAX` | `20` | Stricter limit for protected mutations |
| `RATE_LIMIT_WINDOW_S` | `60` | Limiter window in seconds |
| `MAX_REQUEST_BYTES` | `1000000` | API request-body ceiling |

The built-in limiter is bounded and process-local. Multi-instance deployments must add a
distributed limit at the edge or gateway; Redis is not currently the rate-limit authority.

## LLM providers (MODE A or maintainer)

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Gemini |
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `LLM_PROVIDER` / per-run overrides | Factory default |

## Source discovery

| Variable | Description |
|----------|-------------|
| `TAVILY_API_KEY` | Baseline indexed-web discovery adapter; local env or owner BYOK vault |

OpenAlex scholarly discovery and public GitHub repository discovery require no key in the baseline
implementation and are rate-limited by those public services. HTML/text/JSON/XML/feed/PDF acquisition
uses direct public HTTP and requires no connector credential. See
[source-discovery.md](source-discovery.md). Optional authenticated/private platform connectors are
not bundled and DeepScout never treats OAuth login as permission to research a user's private data.

## Hosted auth (MODE B)

| Variable | Description |
|----------|-------------|
| `SESSION_SECRET` | Session signing secret |
| `CREDENTIAL_ENCRYPTION_KEY` | 32-byte key (raw or urlsafe base64) for BYOK vault |
| `GITHUB_OAUTH_CLIENT_ID` / `SECRET` | GitHub OAuth |
| `GOOGLE_OAUTH_CLIENT_ID` / `SECRET` | Google OAuth |
| `MAINTAINER_VAULT_GITHUB_ID` | GitHub numeric user ID for the operator whose BYOK vault is auto-seeded from maintainer env API keys (hosted only; no other users) |

## Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | local compose | Optional in hosted prod; used for probes in MODE A |

## Research defaults

See `.env.example` for budget limits: `RESEARCH_MAX_ITERATIONS`, `RESEARCH_MAX_COST_USD`, etc.

| Variable | Default | Description |
|----------|---------|-------------|
| `RESEARCH_MAX_COVERAGE_ROUNDS` | `3` | Operator hard cap; mode profiles use Quick 1, Standard 2, Deep 3 |
| `RESEARCH_MAX_GAP_QUERIES_PER_ROUND` | `6` | Operator hard cap; mode profiles use 2 / 3 / 3; Deep adds a third round |
| `RESEARCH_MAX_REPORT_REWRITES` | `3` | Operator hard cap; mode profiles use 1 / 2 / 3 |

The canonical mode profile also bounds requirement tasks, search results per query, and cumulative
embedding/index tokens. See
[agent-runtime.md](agent-runtime.md#quick--standard--deep). Lower operator caps win; learning policy
deltas cannot exceed these bounds.

## Retrieval

| Variable | Default | Description |
|----------|---------|-------------|
| `RETRIEVAL_MODE` | `hybrid` | `lexical`, `dense`, or `hybrid` |
| `RETRIEVAL_TOP_K` | `8` | Final chunks returned |
| `RETRIEVAL_CANDIDATE_K` | `20` | Pre-fusion candidate pool |
| `RETRIEVAL_ROUTER_ENABLED` | `true` | Adaptive intent-based retriever mix |
| `CONTEXTUAL_RETRIEVAL_ENABLED` | `true` | Prefix document/section context for embeddings |
| `RERANKER_MODE` | `deterministic` | `cross_encoder` requires `deepscout-research[rerank]` |

Lexical hybrid uses **BM25** (`retrieval/bm25.py`) and **Postgres FTS** as separate RRF legs — not the same algorithm.

### Embedding and language behavior

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | Resolved provider (`google` in the release env) | Must be `google` or `openai` |
| `EMBEDDING_MODEL` | Provider default | Google default is `gemini-embedding-2` |
| `EMBEDDING_DIMENSIONS` | `768` | Stored vector size; changing it requires reindexing |

The v0.1.3 multilingual benchmark validates the current Google 768-dimensional space directly, so
the release does not change model, dimensions, or embedding config version and requires no reindex.
Language detection and query planning introduce no translation dependency or extra service key.

## LangSmith (optional)

| Variable | Description |
|----------|-------------|
| `LANGSMITH_API_KEY` | Tracing API key |
| `LANGSMITH_TRACING` | `true`/`false` |
| `LANGSMITH_PROJECT` | Project name |

Hosted users control tracing via account settings. The worker establishes a credential-free
process baseline, applies only the owner's vaulted LangSmith configuration for that run, and
restores the baseline afterward; maintainer keys are not used for hosted user research.

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
