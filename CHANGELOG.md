# Changelog

All notable changes to DeepScout are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and releases use
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No unreleased changes yet.

## [0.1.0] - 2026-08-24

First public, versioned DeepScout release.

### Added

- Bounded multi-agent research runtime with explicit research contracts, task DAGs, budgets,
  resumable jobs, human review controls, and persisted execution history.
- Hybrid retrieval across lexical, PostgreSQL full-text, dense vector, and optional compiled
  knowledge paths, with source snapshots and claim-to-evidence provenance.
- Requirement coverage, corrective research, contradiction handling, cited reports, deterministic
  evaluation gates, and a controlled policy-learning loop.
- Local MODE A, authenticated/BYOK MODE B, and a zero-spend read-only public demo catalog.
- Public GHCR images for the API/worker/migration runtime and the Next.js self-hosted frontend,
  published for `linux/amd64` and `linux/arm64` with OCI provenance and SBOM attestations.
- Release compose path with PostgreSQL/pgvector, Redis, one-shot Alembic migration, API, worker,
  and web services.

### Security

- Tenant isolation and non-enumerating authorization in hosted mode.
- Encrypted BYOK storage, bounded tools and autonomy, SSRF-resistant fetches, prompt-injection
  boundaries, secret scanning, Semgrep, dependency audits, and CodeQL.
- Non-root application containers with external runtime configuration and no embedded provider or
  deployment credentials.

### Deployment notes

- Database schema head for this release is Alembic `016`.
- Research execution requires user-supplied model and search provider credentials.
- A persistent API, worker, and PostgreSQL/pgvector database are required; a Vercel-only deployment
  is not a complete DeepScout runtime.

[Unreleased]: https://github.com/francescoveryra-dot/deepscout/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/francescoveryra-dot/deepscout/releases/tag/v0.1.0
