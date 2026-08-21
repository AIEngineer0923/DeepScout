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

DeepScout is a **local trusted single-user** research workstation.

- There is no multi-user authentication, session, JWT, or tenant isolation.
- Any process that can reach the API can create/execute/cancel/export every run.
- Binding the API to a public interface without an authenticating reverse proxy
  is **not a supported production posture**.
- Retrieved web content, model output, and export payloads are untrusted data.

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
- provider keys only in `.env`, never in the browser

Internet-facing deployment requires, at minimum:

- an authenticating reverse proxy or future first-party auth
- HTTPS
- production CORS origins
- `RATE_LIMIT_ENABLED=true`
- `APP_DEBUG=false`
- database credentials that are not the compose defaults
- a review of LangSmith tracing privacy (research text is sent when tracing is on)

## Known accepted limitations

- **No authentication.** UUID knowledge of a run ID is sufficient to read or
  mutate that run on a reachable API. This is accepted for local single-user
  use and is a blocker for public Internet exposure.
- **LangSmith privacy.** When tracing is enabled, goals, retrieved snippets,
  and model I/O may be sent to LangSmith. Secrets and settings blobs are
  redacted; research content is not treated as secret.
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
