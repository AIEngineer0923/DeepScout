# DeepScout deployment

## Architecture decision: MODE A — local / trusted network

DeepScout is an **open-source local research workstation**, not a multi-tenant SaaS.

| Mode | Status |
|---|---|
| **A — local / trusted network** | Supported. This is the intended product. |
| **B — public Internet with first-party auth** | **Not supported.** There is no authentication or authorization boundary. |

Do not bind the API to a public address and call that a cloud product. UUID routes are capabilities: anyone who can reach the API can create, execute, cancel, and export every run.

Production URL and multi-user identity remain TBD (Phase 10+). Until a real identity layer exists, the security gate for public Internet deployment is **FAIL**.

## Supported layouts

1. **Developer workstation** — `uv` + `npm` + Compose Postgres/Redis. API default `API_HOST=127.0.0.1`.
2. **Docker Compose on the same host** — published ports bound to `127.0.0.1` only.
3. **Trusted private network** — place an authenticating reverse proxy in front if more than one operator can reach the host. DeepScout itself still has no users.

## Compose defaults are local-only

`infra/docker/docker-compose.yml` uses `POSTGRES_PASSWORD=deepscout` for disposable local databases.

- Never use that password for a shared or remote database.
- Never publish Compose ports on `0.0.0.0` unless the host firewall and a trusted network already isolate the machine.
- Provide a real `DATABASE_URL` / `REDIS_URL` for anything beyond a laptop.

## Runtime defaults

- `API_HOST=127.0.0.1`
- `APP_DEBUG=false`
- `ENABLE_SMOKE_AGENT=false`
- `LANGSMITH_TRACING=false` (opt in; research text may leave the machine when enabled)
- `RATE_LIMIT_ENABLED=true` in the API container; optional for a single-user `uv` process
- CORS origins must be explicit local web origins, never `*`

## Public Internet

Not a supported DeepScout mode. If you need remote access, terminate TLS and authentication on a gateway you control, keep DeepScout on loopback, and accept that the app still has no per-object authorization.

See [HTTP_PRODUCTION_CONTRACT.md](architecture/HTTP_PRODUCTION_CONTRACT.md) and [SECURITY.md](../SECURITY.md).
