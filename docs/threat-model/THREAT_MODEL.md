# Threat Model

Scope: URL fetch, document handling, tool execution, API, DB, LLM prompts,
exports, CI, containers, and both supported deployment modes: the local
single-operator workstation (MODE A) and authenticated, owner-isolated hosted
workspaces with BYOK credentials and read-only public demos (MODE B).

## Assets

- User research goals (may contain PII)
- API keys (LLM, search, LangSmith)
- Collected sources and snapshots
- Evidence graph integrity
- Infrastructure (DB, Redis, compute cost)

## Trust boundaries

```text
MODE A: [Trusted local operator] → [Web UI] → [Local API] → [Orchestrator]
MODE B: [Browser] → [OAuth/session boundary] → [Owner-scoped API] → [Orchestrator]
             [Anonymous browser] → [Read-only published demo API]
                                                     ↓
                                              [PostgreSQL]
                                                     ↓
                                      [BYOK providers / secure fetch]
                                                     ↓
                                        [LangSmith traces, opt-in]
```

Untrusted: Internet content, model outputs before verification, export
consumers (spreadsheet formula parsers).

## Threat catalog

| ID | Threat | Vector | Impact | Mitigation |
|---|---|---|---|---|
| T1 | SSRF | malicious URL | internal network scan | DNS+IP validation, blocked ranges, connect-time IP pinning |
| T2 | DNS rebinding | TTL flip after check | SSRF bypass | pin TCP connect to the checked IP |
| T3 | Redirect abuse | 302 chain | SSRF | re-resolve and re-pin each hop |
| T4 | Prompt injection | page/goal content | tool misuse | DATA blocks, phase tool allowlists |
| T5 | Tool injection | tampered tool output | wrong actions | schema validation, no eval |
| T6 | Malicious HTML/files | XSS, parser bugs | user harm | text extraction, no raw HTML render, size caps |
| T7 | Decompression bomb | gzip bomb | DoS | bounded decompress |
| T8 | Path traversal | upload filename | FS escape | no upload API; UUID keys |
| T9 | Secret exfiltration | prompt trick | key leak | never inject secrets; log/trace redaction |
| T10 | XSS | report in UI | workstation compromise | React text, CSP, no `dangerouslySetInnerHTML` |
| T11 | SQL injection | API params | DB breach | SQLAlchemy ORM / bound parameters |
| T12 | Rate abuse | spam runs | DoS / cost | optional IP rate limits; production default on |
| T13 | Denial-of-wallet | infinite loop | API cost | ResearchBudget hard stops |
| T14 | PII in logs | verbose logging | privacy | redaction; no claim of GDPR certification |
| T15 | Supply chain | bad dependency | breach | Dependabot, npm/pip audit, CodeQL, Semgrep |
| T16 | Unauthenticated MODE A API exposed remotely | bind local mode to `0.0.0.0` | full data/cost access | default bind localhost; document local mode as an unsupported Internet posture |
| T17 | CSV formula injection | export | spreadsheet code exec | prefix sanitization |
| T18 | Checkpoint cross-run | forged thread id | state mix | `run_id:task_id` thread IDs; domain DB authoritative |
| T19 | LangSmith data export | tracing left on | research text leaves host | default `LANGSMITH_TRACING=false`; key-name redaction; documented opt-in |
| T20 | Retrieval poisoning | malicious snapshot text in index | wrong evidence / prompt injection | chunks are DATA; untrusted wrapper; injection markers flagged |
| T21 | Cross-run vector leakage | forged run_id / chunk id | data from other runs | mandatory `research_run_id` filter in all retrieval SQL; tests |
| T22 | Embedding denial-of-wallet | unbounded re-embed / re-retrieve | cost spike | idempotent indexing; bounded re-retrieval; usage accounting |
| T23 | Incompatible embedding spaces | mixed models/dims | nonsense similarity | `provider+model+dimensions+config_version` unique constraint |
| T24 | Rerank/query-rewrite injection | poisoned candidate text | policy override | no LLM reranker v1; deterministic rerank only |
| T25 | Follow-up / report injection | historical prose in follow-up context | tool/budget/monitor abuse | bounded DATA slice; authority remains snapshots |
| T26 | Source pin/exclude bypass | URL aliases, www, vector re-entry | excluded evidence reused | canonical URLs; retrieval exclusion; pin ≠ verified |
| T27 | Monitor DoW / schedule explosion | injected “create monitor every second” | unbounded spend | API-only monitor CRUD; max 25; leases; per-run budget |
| T28 | Knowledge graph DoS | unbounded hops/cycles | API stall | max 3 hops; node/edge caps |
| T29 | Run-diff cross-run mix | guessing UUIDs | foreign research disclosure | compare requires two existing run IDs and hosted owner authorization for both |
| T30 | RUM abuse / high cardinality | unbounded routes, research text | DB growth | allowlisted path, rate limit, no payload text |
| T31 | SSE Last-Event-ID abuse | huge/negative cursors | extra reads | integer sequence cursor; durable log is run_events |

## RAG content rule

> Retrieved chunks are DATA, never trusted instruction. Embedding rows are not evidence.

Hierarchy:

```text
SYSTEM SECURITY POLICY > ROLE POLICY > TASK > DOMAIN STATE > RETRIEVED CANDIDATES > RAW EXTERNAL CONTENT
```

Retrieved text cannot grant tools, change budget, verify claims, or alter prompts.

## Content rule

> Retrieved content is DATA, never trusted instruction.

## Mode B hosted additions

| ID | Threat | Mitigation |
|---|---|---|
| T32 | IDOR/BOLA | Server-side owner match; 404 for foreign ids |
| T33 | Cross-user RAG/Wiki/SSE | Authorize run before retrieval, wiki, events |
| T34 | Credential theft / exfil | AES-GCM vault, no read-back, redaction |
| T35 | Maintainer key fallback | Hosted overlay zeros env keys |
| T36 | OAuth CSRF / open redirect | PKCE + state; allowlisted `next` |
| T37 | Session theft | HttpOnly Secure SameSite cookies |
| T38 | Demo mutation | Write paths denied for `is_public_demo` |
| T39 | Prompt-injection tenant escape | Owner is never model-selected |
| T40 | Denial of wallet (host) | Per-IP rate limits, concurrent run caps |
| T41 | Preview secret leak | Fork PRs do not receive production secrets |
| T42 | Next.js cache leak | `no-store` on authenticated fetches |
| T43 | Cross-tenant learning decision | Candidate approve/reject updates require the authenticated owner id and return 404 on mismatch |
| T44 | Synthetic policy promotion by regular users | Controlled learning-smoke promotion is limited to local mode or the configured hosted operator |
