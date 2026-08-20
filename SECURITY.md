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

## Security principles

1. **Retrieved content is DATA, never trusted instruction**
2. **No secrets in Git** — run `bash scripts/scan-secrets.sh` before push
3. **No secrets in observability** — LangSmith, logs, SSE, errors
4. **Bounded autonomy** — hard research budgets
5. **Evidence before authority** — LLM output ≠ fact without evidence link

## Threat model

[docs/threat-model/THREAT_MODEL.md](docs/threat-model/THREAT_MODEL.md)

## CI security checks

- Secret pattern scan (`scripts/scan-secrets.sh`)
- Dependency updates via Dependabot (GitHub Actions ecosystem)
- Additional SAST/CodeQL planned for Phase 1+

## AI-specific risks

- Prompt injection from retrieved sources
- Hallucinated citations
- Denial-of-wallet via unbounded loops

Mitigations: orchestrator budgets, evidence graph, secure fetch pipeline, verification stages.
