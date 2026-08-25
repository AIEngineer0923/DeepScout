# Changelog

All notable changes to DeepScout are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and releases use
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No unreleased changes yet.

## [0.1.6] - 2026-08-25

### Fixed

- Anonymous visitors can open every published demo plan even though the public workspace
  intentionally omits internal task tool assignments.
- Public report pages no longer advertise owner-only Markdown/PDF export routes.
- Repository-facing version labels, release instructions, architecture/environment references,
  evaluator count, claim semantics, SSE/fetch architecture, container defaults, and the complete
  changelog now agree with the implemented release.

## [0.1.5] - 2026-08-25

### Security

- OAuth callbacks are bound to the initiating browser; public demos expose only sanitized,
  read-only projections; hosted LangSmith credentials are scoped to the owning run.
- HITL decisions, run/monitor quotas, budget accounting, and SSE lifecycle controls are
  concurrency-safe and bounded.
- Retrieved content receives multilingual prompt-injection filtering; PDF and XML parsing are
  isolated and bounded; factual verification requires corroboration from distinct sources.
- Redirect, Markdown URL, rate-limit identity, and public-evaluation mutation boundaries were
  hardened with negative regression coverage.

### Changed

- Research budgets now enforce hard maxima and elapsed wall time.
- The API runtime uses a pinned Alpine base; release Compose services are non-root, read-only,
  capability-free, and protected by `no-new-privileges`.
- Release publication scans images for HIGH/CRITICAL vulnerabilities and emits SBOM, provenance,
  and GitHub attestations for amd64 and arm64 manifests.

## [0.1.4] - 2026-08-24

### Fixed

- HTML acquisition now keeps the document body when a non-empty `<title>` precedes `<main>` or
  `<article>`. This restores evidence snapshots for Sphinx and other documentation sites while
  continuing to exclude scripts, navigation, and other non-content regions.
- Technical uses of the word `build` no longer turn explanatory research into an entity-set
  deliverable, while imperative portfolio construction remains structured and validated.
- Native multilingual discovery queries now retain deterministic official/primary-source policy;
  Italian, French, German, and Spanish official-documentation wording is recognized directly.
- Quick discovery now reserves one bounded deterministic fallback when only one query language is
  planned: the precise native query runs first, followed by a relaxed version that removes brittle
  quoted/site-path syntax without discarding the requested domain or planned language.
- Search-result relevance keeps dotted version/decimal identifiers intact and recognizes planned
  multilingual variants after deterministic source-policy enrichment.
- English `shortlist of exactly N` requests now retain their exact cardinality; an instruction to
  provide an excluded alternative is not mistaken for a named exclusion, and generic table
  headings or measurements are not promoted as entity finalists.
- Run-scoped search preference routing now preserves the planner's query-language metadata instead
  of resetting enriched native-language requests to `und`.
- Language execution summaries and evidence metadata match policy-enriched queries back to their
  planned native variants instead of relying on brittle byte-for-byte equality.
- Allocation parsing no longer mistakes league/audience sizes or modifier comparisons for budget
  totals and category quotas.
- Scoring thresholds such as "every 4 points" are excluded from allocation quotas, and compound
  comparison instruction prose no longer becomes a brittle literal report-presence constraint.

## [0.1.3] - 2026-08-24

### Added

- Contract schema v3 classifies entity sets, shortlists, rankings, portfolios, allocations,
  itineraries, and comparisons by requested output shape rather than subject-specific keywords.
- A persisted, domain-neutral `EntityResearchMatrix` records entity attributes, confidence,
  freshness, source/evidence provenance, sparse-field status, and conflict state.
- A persisted source-to-deliverable funnel records discovery, fetch, indexing, retrieval,
  evidence admission/rejection, claims, and populated matrix fields with bounded reason codes.
- Deterministic selection and final-deliverable checks cover exact item counts, category quotas,
  budgets, include/exclude rules, comparison subjects, and Markdown allocation arithmetic.
- Follow-up runs now carry an explicit continuation type, parent report/evidence lineage,
  bounded matrix context, and provenance-preserving snapshot reuse where freshness is not requested.
- Material conflicting constraints can create a real human-input review; a response resolves the
  chosen value, resumes the same run, and remains idempotent across reloads.
- Goal-conditioned multilingual plans distinguish user, output, query, and original source
  languages and persist native query variants plus language execution metrics.
- A multilingual retrieval benchmark covers cross-language semantic pairs, localized aliases,
  identifiers, and a no-answer negative across lexical, dense, RRF, and reranked ablations.

### Changed

- Evidence extraction is attribute-aware, reuses multiple requirement-scoped queries per acquired
  source, records rejection causes, and concentrates the report context on viable entities.
- Partial but admissible source contributions no longer block every dependent task; portfolio
  inadequacy remains visible to coverage and bounded corrective research.
- Quick mode uses one research task and skips global replanning, while preserving evidence and
  report finalization budgets.
- Reports are answer-first and entity deliverables use a mechanically inspectable Markdown table;
  deliverable completeness is tracked separately from evidence completeness.
- Source snapshots and evidence preserve the original language/text/URL/locator; report-language
  synthesis remains derived presentation, and cross-language dense candidates are not discarded by
  language-local lexical overlap.

### Security

- Follow-up reuse remains tenant-authorized, copies only bounded source snapshots with explicit
  lineage, and does not treat parent report prose as evidence.
- Existing tenant isolation, BYOK, SSRF, public-demo read-only, prompt-injection, and authoritative
  HITL resolution controls remain covered by the full security suite.

### Deployment notes

- Database schema head is Alembic `017`; run `alembic upgrade head` before starting v0.1.3 API and
  worker processes.

## [0.1.2] - 2026-08-24

### Fixed

- Generic questions that merely mention an API no longer activate repository discovery; code and
  technical-documentation connectors now require an actual software, SDK, repository, package, or
  framework intent.
- The Dashboard research composer and the sidebar **New Research** screen now create and enqueue
  runs through one shared launch path with identical default research preferences and visible error
  handling.

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

[Unreleased]: https://github.com/francescoveryra-dot/deepscout/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/francescoveryra-dot/deepscout/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/francescoveryra-dot/deepscout/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/francescoveryra-dot/deepscout/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/francescoveryra-dot/deepscout/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/francescoveryra-dot/deepscout/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/francescoveryra-dot/deepscout/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/francescoveryra-dot/deepscout/releases/tag/v0.1.0
