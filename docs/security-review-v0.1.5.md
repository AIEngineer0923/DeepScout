# DeepScout 360° security review — v0.1.5

Review date: 2026-08-25

Scope: DeepScout source, API, worker, web client, persistence, retrieval and source
fabric, agent runtime, HITL, learning/evaluation paths, OAuth/BYOK, public demos,
streaming, PostgreSQL/pgvector, Redis integration, containers, CI, release workflow,
GHCR artifacts, and supported local/hosted deployment modes.

The external Master IAF Agent OS was used as operating guidance. It is not copied into
this repository and does not replace DeepScout's repository-local invariants.

## Threat model

DeepScout processes hostile goals, web pages, documents, search results, model output,
citations, and human review text. The principal threat actors are:

- anonymous Internet users probing hosted auth, public demos, operational endpoints, and
  browser rendering;
- authenticated tenants attempting cross-tenant reads, quota abuse, wallet exhaustion,
  session persistence, or credential confusion;
- malicious sources attempting SSRF, parser denial of service, indirect prompt injection,
  evidence poisoning, citation laundering, or learning-loop influence;
- compromised dependencies, CI actions, base images, or mutable release artifacts;
- operators accidentally exposing MODE A or maintainer credentials in hosted execution.

Security boundaries are principal ownership in MODE B, explicit read-only publication,
the encrypted BYOK vault, deterministic orchestration and budget gates, source snapshots,
evidence provenance, and immutable release inputs.

## Remediated findings

### Critical/high-impact

- Browser-unbound OAuth state allowed login-CSRF/session swapping. State is now mirrored
  in an HttpOnly, Secure-when-HTTPS, SameSite=Lax callback-path cookie and compared before
  database state consumption. Expired states are cleaned and consumption is row-locked.
- Public-demo status previously granted anonymous access through generic run-read
  authorization. Anonymous reads are now explicitly scoped to sanitized run, summary,
  workspace, and snapshot presentation. Events, HITL reviews, exports, evaluations,
  preferences, SSE, and knowledge internals remain owner-only.
- Process-global LangSmith variables could route tenant traces through maintainer
  credentials. Hosted processes now keep a credential-free baseline and install only the
  current owner's vaulted tracing configuration for the duration of that run.
- Wall-clock budget existed in the schema but was not enforced against actual elapsed
  time. Planning, iterations, tools, source admission, and phase transitions now stop at
  the elapsed-time limit without provider-backed finalization.
- Quote existence was treated as full factual verification. A resolved single-source
  quote is now partial verification; full verification requires matching evidence from
  at least two distinct sources.
- API-requested budgets accepted impractically large values. Every budget dimension now
  has a hard application maximum.
- The released Debian API image included unused vulnerable Perl packages. The image now
  uses a pinned Python 3.12 Alpine base and contains no Perl runtime.

### Medium-impact

- Concurrent HITL decisions could apply more than once. Review resolution is serialized
  with a row lock, and pending-review creation is serialized on the run row.
- Existing SSE connections survived logout/revocation and replay was unbounded. Hosted
  streams revalidate the session and owner every loop; replay is capped at 200 events per
  query.
- Monitor limits were global and run quota checks raced. Hosted monitor counts are
  principal-scoped, and PostgreSQL advisory transaction locks serialize monitor/run
  quota checks with creation and monitor dispatch.
- PDF parsing happened in the long-lived worker. Parsing now uses a spawned subprocess
  with byte, page, output, CPU, memory, and wall-time bounds.
- Source normalization admitted arbitrary MIME types as text. PDF, JSON, XML, HTML, plain
  text, Markdown, and CSV now require explicit type or recognized magic.
- Injection detection was English-only. Retrieval text is Unicode-normalized, control
  characters are stripped, common multilingual override phrases are flagged, and flagged
  chunks are excluded from model prompt context while remaining available for audit.
- Browser redirect and Markdown handling accepted backslash/control/protocol-relative
  variants. Both server and client now reject them.
- Public demo reads could backfill evaluation rows. Public workspace reads no longer
  perform evaluation persistence.
- In-process rate-limit memory could exceed its configured key bound. New identities are
  rejected once the bounded map is full after stale eviction; every request uses its
  client-address bucket, and unvalidated session cookies cannot mint identities.
  OAuth-start and learning/evaluation mutations receive the stricter limit.

## Controls verified

- Private cross-tenant run reads and writes return 404.
- Public-demo mutations are denied before request-body validation.
- Hosted provider calls clear operator model/search credentials and load only the run
  owner's vault records.
- Vault records use AES-GCM with principal, provider, and key-version associated data.
- Session tokens are high entropy, stored as hashes, expiry checked, and rejected for
  inactive principals.
- Secure fetch resolves and validates public IPs, pins the connection target, keeps TLS
  hostname verification, limits redirects and bytes, and rejects private/metadata ranges.
- Worker tools are code-allowlisted; model text cannot grant tools or budget.
- Claims and evidence remain run-scoped and evidence quotes resolve to immutable snapshots.
- Public browsing does not invoke model/search providers.
- HTML/Markdown output is sanitized and unsafe URL schemes are rejected.
- Release actions are commit-pinned; Python and npm dependencies are locked.
- Release images run non-root and publish OCI metadata, SBOM, provenance, and GitHub
  attestations.

## Residual risks and deployment obligations

- The application rate limiter is process-local. Multi-instance hosted deployments need
  a distributed edge/gateway limit and connection limits for SSE.
- A synchronous provider request already in flight cannot be forcibly interrupted by the
  orchestrator's wall-clock check. Provider HTTP timeouts and infrastructure job timeouts
  remain the outer bound.
- Source corroboration improves evidence integrity but does not prove objective truth;
  copied misinformation across independent domains remains possible.
- Learning candidates can be influenced by poisoned observations. They remain owner-scoped,
  trust-labeled, evaluation-gated, and subject to human approval; automatic production
  policy promotion should remain disabled without signed datasets and stronger provenance.
- Application-layer vault encryption does not protect plaintext while a worker is using a
  key. Host/database administrators remain trusted operators.
- MODE A intentionally has no authentication and must not be Internet-exposed.
- CSP still requires framework-generated inline script/style compatibility. XSS protection
  therefore also depends on React escaping, Markdown sanitization, no raw HTML, and strict
  URL handling.
- GitHub secret scanning and push protection are enabled. GitHub reported non-provider
  patterns and validity checks as disabled after an enable request, so those optional
  platform features remain dependent on account/repository entitlement.

## Release gates

v0.1.5 must not be published unless:

- repository secret scan, Ruff, non-integration pytest, frontend tests/build, Semgrep,
  pip-audit, npm audit, CodeQL, retrieval/learning gates, and Alembic head pass;
- API and web images build for amd64 and arm64;
- image scanning reports no HIGH or CRITICAL vulnerability;
- image runtime identity is non-root and the API image has no Perl executable;
- self-hosted migration, API readiness, worker startup, and web health pass;
- GitHub release version, source revision, GHCR OCI labels, SBOM, provenance, and
  GitHub attestations all resolve to the same tagged commit.
