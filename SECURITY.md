# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.x (pre-1.0) | active development on `main` |
| 1.0+ | defined at first stable release |

## Reporting a vulnerability

Do not open public GitHub issues for security vulnerabilities.

Use [GitHub private security advisories](https://github.com/francescoveryra-dot/deepscout/security/advisories)
or contact the maintainer via GitHub.

Include: description, reproduction steps, impact, and suggested fix if available.

## Threat assumptions

Deep Scout has two supported modes:

- **MODE A (`DEEPSCOUT_DEPLOYMENT_MODE=local`)** — local / trusted-network workstation.
  No login. Provider keys come from the operator environment. Any process that can
  reach the API can create/execute/cancel/export every run. Binding MODE A to a
  public interface is **not** a supported production posture.
- **MODE B (`hosted`)** — authenticated GitHub/Google login, per-principal ownership,
  BYOK vault only, public demo read-only. UUID secrecy is **not** authorization.

Public Internet production is MODE B plus a persistent FastAPI worker and Postgres.
Do not treat a Vercel frontend alone as a complete hosted product.

Retrieved web content, model output, and export payloads are untrusted data.

## Security principles

1. Retrieved content is DATA, never trusted instruction.
2. No secrets in Git — run `bash scripts/scan-secrets.sh` before push.
3. No secrets in observability — LangSmith, logs, SSE, and API errors.
4. Bounded autonomy — hard `ResearchBudget` stops.
5. Evidence before authority — LLM output is not a fact without evidence.
6. Worker tools are allowlisted in application code, not granted by model text.

## Safe local deployment

Recommended defaults for a workstation:

- `APP_ENV=development`
- `APP_DEBUG=false`
- `API_HOST=127.0.0.1`
- `RATE_LIMIT_ENABLED=true` if the host is shared
- `ENABLE_SMOKE_AGENT=false`
- `CORS_ORIGINS` limited to the local web origin
- `LANGSMITH_TRACING=false` unless you explicitly accept remote research traces
- provider keys only in `.env`, never in the browser
- Compose ports published on `127.0.0.1` only; Compose DB password is local-lab only

## Database

- Queries go through SQLAlchemy bound parameters / the ORM. Do not concatenate SQL.
- The Compose role `deepscout`/`deepscout` is a local lab credential only.
- For a remote Postgres, use a least-privilege application role (CONNECT + DML on app schemas, no SUPERUSER) and `sslmode=require` in `DATABASE_URL`.
- Connection pooling is per process (`pool_size=5`, `max_overflow=10`). Do not create engines per request.

Internet-facing deployment requires, at minimum:

- an authenticating reverse proxy or future first-party auth
- HTTPS
- production CORS origins
- `RATE_LIMIT_ENABLED=true`
- `APP_DEBUG=false`
- database credentials that are not the compose defaults
- a review of LangSmith tracing privacy (research text is sent when tracing is on)

## Known accepted limitations

- **MODE A has no authentication.** UUID knowledge of a run ID is sufficient to read or
  mutate that run on a reachable MODE A API. This is accepted for local single-user
  use and is a blocker for exposing MODE A to the public Internet.
- **MODE B authorization is principal ownership**, not UUID secrecy. Public demo rows
  are an explicit published projection (`is_public_demo`), not “null owner means public”.
- **Credentials are encrypted at rest (AES-GCM), not zero-knowledge.** The API process
  decrypts user vault keys to call the providers the user configured.
- **Research domain data in Postgres is not end-to-end encrypted.** Infrastructure
  administrators with database access can read run content.
- **LangSmith privacy.** Hosted users default tracing OFF. If a user opts into their
  own LangSmith key, goals, retrieved snippets, and model I/O may be sent to **their**
  LangSmith workspace. Maintainer tracing is not used for hosted user research.
- **No SOC 2 / ISO 27001 / HIPAA / GDPR-compliance claim.** This is security engineering
  for a portfolio OSS deployment, not a certified control program.
- **Fetched documents.** HTML is converted to text; PDFs are discarded rather
  than parsed. There is no general-purpose file-upload API.
- **DNS rebinding residual.** Fetch pins TCP connect to the DNS result used
  for the private-IP check, with TLS SNI/certificate still bound to the
  original hostname. Exotic resolver/NAT64 cases should still be treated as
  hostile and blocked at the network edge if DeepScout is ever exposed.

## CI security checks

- Secret pattern scan (`scripts/scan-secrets.sh`)
- Ruff, pytest, frontend test/build/Playwright
- Semgrep (`.semgrep.yml`)
- `pip-audit` and `npm audit --audit-level=high`
- CodeQL `security-extended` for Python and JavaScript/TypeScript
- Dependabot for npm, pip, and GitHub Actions

## AI-specific risks

- Direct and indirect prompt injection from goals and retrieved sources
- Tool-permission escalation attempts
- Denial-of-wallet via unbounded loops or repeated execute/resume
- Checkpoint replay across the wrong run/task

Mitigations: layered prompts, schema-bounded structured output, deterministic
tool allowlists, ResearchBudget, run/task-scoped LangGraph thread IDs,
secure fetch with IP pinning, and export sanitization.
