# Changelog

All notable changes to DeepScout are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and releases use
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No unreleased changes yet.

## [0.1.1] - 2026-08-24

### Added

- General-purpose source fabric with a capability registry, goal-conditioned query families,
  capability-aware fallback routing, OpenAlex scholarly discovery, and GitHub public
  repository/README discovery alongside indexed web search.
- Multi-source portfolio stopping based on independent publishers, source-kind diversity,
  contradiction search, low marginal yield, mode budgets, and explicit user source constraints.
- Bounded normalization and provenance for HTML, text, JSON, XML, RSS/Atom, PDFs, and public video
  metadata/captions when accessible, plus source-aware frontend labels and portfolio evaluations.

### Fixed

- Workers now retry zero-yield or irrelevant searches with bounded, subject-preserving generic
  reformulations and account for every attempt against tool budgets.
- Research tasks require an actual admissible-source contribution before becoming completed;
  zero-yield tasks become blocked and terminal dependency failures propagate through the DAG.
- Semantic planner DAGs are no longer fragmented into one mechanical task per long-request bullet.
- Stale checkpoints can no longer convert `sources_added: 0` into a successful task.
- Terminal events, evaluation results, learning diagnosis, and localized frontend outcomes now agree
  on completed, partial, evidence-blocked, budget-exhausted, and technical-failure states.
- Numeric user constraints are persisted in contract schema v2; conflicting totals are disclosed and
  allocation-table arithmetic is checked deterministically.

### Security

- Existing tenant isolation, BYOK, SSRF, public-demo read-only, tool allowlist, and budget invariants
  remain unchanged and are covered by the full security suite.
- Structured connector responses, document downloads, XML entity declarations, PDF page traversal,
  redirects, and public-video transcript acquisition are bounded and reuse the existing public-URL
  and DNS-pinning controls.

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

[Unreleased]: https://github.com/francescoveryra-dot/deepscout/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/francescoveryra-dot/deepscout/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/francescoveryra-dot/deepscout/releases/tag/v0.1.0
