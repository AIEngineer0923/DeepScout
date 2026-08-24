# Source discovery architecture

DeepScout uses a capability-aware source fabric. It does **not** equate Internet research with one
web-search request, and it does not claim universal access to every platform.

```text
ResearchRequirement
  → SourceStrategy (goal, mode, source constraints, evidence need)
  → query families (exact, primary, independent, data, recent, academic, code, video/community)
  → DiscoveryRouter
  → ConnectorRegistry
  → candidate sources
  → relevance + authority + access-policy admission
  → secure fetch / structured acquisition
  → content normalizer
  → immutable SourceSnapshot
  → claims / evidence / synthesis
```

Discovery and acquisition are separate. An indexed web search may discover a PDF, repository,
video, feed, dataset, or community page; the appropriate acquisition path then obtains the original
content when it is publicly and lawfully accessible. Search-result snippets remain candidate hints,
not evidence.

## Connector registry

| Connector | Source class | Discovery | Fetch / normalize | Authentication | Hosted / self-hosted | Limits |
|---|---|---|---|---|---|---|
| `indexed_web` | Web, official, news, video, community and other indexed public URLs | Configured Tavily adapter | No; hands original URL to acquisition | Tavily key through local env or owner's hosted BYOK vault | Yes / yes | Index coverage and freshness are provider-dependent |
| `openalex` | Scholarly works | OpenAlex public REST API | Structured metadata and available abstract become a snapshot; citation resolves to DOI/landing page | None for baseline public access | Yes / yes | Abstract/full-text availability varies; rate limits apply |
| `github_public_api` | Public repositories and README documentation | GitHub public REST search | Structured repository metadata and public README | None for baseline public data | Yes / yes | Public repositories only; unauthenticated GitHub limits apply |
| `secure_http` | HTML, plain text, JSON, XML, RSS/Atom | Direct/discovered URL | DNS-pinned SSRF-safe HTTP and bounded normalizers | None | Yes / yes | No login, CAPTCHA, paywall, or access-control bypass |
| `pdf_document` | Public PDF reports and papers | Direct/discovered URL | Bounded `pypdf` text extraction with page locators | None | Yes / yes | No OCR for scanned-image-only PDFs; encrypted PDFs may be unavailable |
| `public_video_page` | Public YouTube/video page | Indexed web or direct URL | Public metadata; public caption track with timestamps only when the page exposes one without access bypass | None | Yes / yes | No private/age-gated content; no transcript is claimed when captions are unavailable |

This table is a registry of implemented capabilities, not a platform allowlist. A new discovery or
content connector implements the common protocol and registers capabilities; planner, evidence and
report core do not require platform branches.

## Source strategy and portfolio policy

The strategy derives useful source kinds from the research contract, requirement semantics, source
constraints and selected mode. Authority, relevance, freshness, independence, and evidence type are
kept separate.

- Quick performs a minimal sufficient portfolio and at least one query family.
- Standard targets multiple independent publishers, uses at least two materially distinct query
  families, and searches for independent/counter evidence.
- Deep increases independent-publisher, source-kind, and query-family targets.

The targets are stopping inputs rather than fixed URL quotas. A task stops when the goal-conditioned
portfolio is adequate, or when bounded query families reach low marginal yield or a hard research
budget ends. A first useful result starts evidence collection; it does not by itself stop a Standard
or Deep task.

Publisher-family normalization prevents multiple pages from one publisher from counting as
independent corroboration. Candidate URLs remain available, but task admission is diversity-aware
and caps repeated publisher-family intake when alternatives exist.
Fetch ordering keeps authority, search relevance, and goal-conditioned source-type fit as separate
signals. It round-robins query families so one high-scoring lane cannot starve the rest of the
planned portfolio.

## Formats and provenance

| Content | Normalization | Locator/provenance |
|---|---|---|
| HTML | Deterministic visible main text plus public author/publisher/date metadata when present | Original/final URL and content hash |
| Plain text | Bounded UTF text | Original/final URL and content hash |
| JSON | Bounded key path/value tree | Structured API record URL |
| XML, RSS, Atom | Bounded element text plus available author/date metadata | Original feed/document URL |
| PDF | `pypdf` text extraction | `[Page N]` markers and page locator scheme |
| GitHub | Public API metadata plus README | Original repository/README URL and API record |
| OpenAlex | Metadata plus available abstract | DOI/landing URL and OpenAlex record |
| Public video | Metadata and accessible caption text | Original video URL; `[HH:MM:SS]` transcript locators when available |

Structured connector records are persisted directly as SourceSnapshots. Web-discovered originals are
fetched before evidence extraction. A discovered source that cannot be acquired remains discovered;
it does not become evidence.

## Failure and fallback behavior

Internal acquisition failures distinguish `auth_required`, `rate_limited`, `removed`,
`unsupported_content`, `paywalled`, `blocked`, `parser_failure`, and generic unfetchable content.
The ordinary UI presents a safe human state rather than backend exception details.

For a compatible strategy, discovery providers are attempted independently. An indexed-search
outage does not suppress OpenAlex or GitHub public discovery. If only one compatible capability is
configured, its failure is reported honestly. Source constraints remain authoritative: an
official-only request is never silently weakened to community evidence.

## Security and access boundaries

- URLs pass public-scheme, private/metadata-network, redirect, and DNS-pinning checks.
- Downloads and decompressed text are bounded; PDF pages, XML/JSON traversal and snapshot size are
  bounded.
- Retrieved content remains untrusted data and never grants tool or workflow authority.
- Raw HTML/scripts are never rendered by the frontend.
- Baseline structured connectors use only public data. Tavily remains owner-scoped BYOK in hosted
  mode. No connector reuses another tenant's credentials.
- DeepScout does not bypass authentication, CAPTCHA, robots/platform restrictions, private profiles,
  paywalls, or API permissions.

## Dependency audit

The only new runtime parsing dependency in v0.1.1 is `pypdf` (bounded to major version 6). It is pure Python, BSD-3-Clause,
supports the repository's Python range, and avoids native amd64/arm64 divergence. JSON and XML/feed
normalization use the Python standard library; GitHub and OpenAlex use the existing `httpx`
dependency. No unofficial social SDK, browser automation, or transcript package was added.

## External limitations

Public indexed discovery can identify Reddit and other community/social URLs, but direct acquisition
depends on the platform's public representation and policies. DeepScout does not advertise a direct
TikTok, Instagram, Facebook, X, or Reddit API connector where none is configured. YouTube's official
caption-download API requires authorization associated with the video; the baseline path therefore
captures only public page data/captions actually exposed without bypass and records when a transcript
is unavailable. Paywalled papers may contribute public scholarly metadata/abstracts, never invented
full text.

References: [OpenAlex help](https://help.openalex.org/),
[GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api),
[YouTube caption authorization](https://developers.google.com/youtube/v3/docs/captions/download), and
[`pypdf` on PyPI](https://pypi.org/project/pypdf/).
