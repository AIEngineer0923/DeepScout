# ADR 011 — Mode B hosted multi-user, public demo, and BYOK

## Problem

DeepScout was a local MODE A workstation. PR #36 closed the product/runtime surface.
This ADR records MODE B: optionally hosted authenticated research, a public read-only demo,
and self-host, without becoming a commercial SaaS.

## Decision

### Modes

- **MODE A (`DEEPSCOUT_DEPLOYMENT_MODE=local`)** — default. No account. Env provider keys. Loopback bind.
- **MODE B (`hosted`)** — authentication required. Per-user ownership. User vault credentials only.
- **PUBLIC DEMO** — `is_public_demo` + `public_slug`. Anonymous read-only. Zero provider spend.

Hosted with missing `SESSION_SECRET`, `CREDENTIAL_ENCRYPTION_KEY`, or OAuth clients **fails closed**
(503 on auth-required routes). It never silently becomes MODE A.

### Auth library

**Chosen: Authlib OAuth 2.1 Authorization Code + PKCE** in FastAPI, with server-side sessions in PostgreSQL.

Rejected:

- **Auth.js** — session cookies are Auth.js-encrypted JWEs. FastAPI cannot independently verify them
  without cloning Auth.js crypto. FastAPI is the authorization plane.
- **Better Auth** — TypeScript-only session hashing. Same split-backend problem.
- **Passwords / magic link** — not justified for GitHub+Google portfolio login.

Sessions: random token, SHA-256 stored, HttpOnly cookie `ds_session`, Secure on HTTPS, SameSite=Lax.
Account linking requires verified email. Unverified email is never an identity merge key.

### Tenant model

`principals.id` is the owner. One personal principal per user. No fake organizations.

`research_runs.owner_principal_id` is the tenancy root. Child rows inherit via `research_run_id`.
Templates and monitors have their own owner FK.

NULL owner is **not** public. Public demo is an explicit flag.

Existing MODE A rows are backfilled to `LOCAL_SYSTEM_PRINCIPAL`.

**RLS:** evaluated and deferred. SQLAlchemy pooling + LISTEN/NOTIFY make session `SET ROLE` fragile.
Scoped repositories + exhaustive A/B tests are the enforcement layer.

Every run-scoped route (including cancel, resume, restart, fork, export, evaluations,
snapshots, SSE, HITL, knowledge page/statement/search/graph) calls `authorize_run`.
Monitors and templates have matching owner checks. Public demo writes return 403.

### BYOK

Hosted research uses only `provider_credentials` decrypted with AES-GCM (cryptography AEAD),
associated data `principal_id:provider:v{key_version}`. Maintainer env keys are zeroed in
`resolve_run_settings`. LangChain is a library — there is no LangChain API key.

### Vercel

Long research, SSE, LISTEN/NOTIFY, and the worker loop do not fit Vercel Function lifetime.
**Selected architecture: VERCEL_WEB_PLUS_PERSISTENT_RUNTIME** — Next.js on Vercel; FastAPI/worker/Postgres
on a persistent host. Cron may wake the scheduler; PostgreSQL remains source of truth.

## Consequences

- Local clone path stays first-class.
- Hosted GitHub/Google login requires operator OAuth apps (external console).
- Public demo can be served even when Gemini/Tavily are down.
