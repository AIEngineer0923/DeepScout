# Threat Model

Scope: URL fetch, document handling, tool execution, API, DB, LLM prompts,
exports, CI, containers. DeepScout is currently a local trusted single-user
research workstation.

## Assets

- User research goals (may contain PII)
- API keys (LLM, search, LangSmith)
- Collected sources and snapshots
- Evidence graph integrity
- Infrastructure (DB, Redis, compute cost)

## Trust boundaries

```text
[Trusted local user] → [Web UI] → [API, no auth] → [Orchestrator]
                              ↓                         ↓
                         [PostgreSQL]            [Tools/Fetch → Internet]
                              ↓
                         [LangSmith traces, optional]
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
| T16 | Unauthenticated remote API | bind `0.0.0.0` | full data/cost access | default bind localhost; document as unsupported Internet posture |
| T17 | CSV formula injection | export | spreadsheet code exec | prefix sanitization |
| T18 | Checkpoint cross-run | forged thread id | state mix | `run_id:task_id` thread IDs; domain DB authoritative |
| T19 | LangSmith data export | tracing left on | research text leaves host | default `LANGSMITH_TRACING=false`; key-name redaction; documented opt-in |

## Content rule

> Retrieved content is DATA, never trusted instruction.
