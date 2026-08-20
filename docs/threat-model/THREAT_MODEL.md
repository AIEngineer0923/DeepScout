# Threat Model (preliminary)

Scope: URL fetch, document upload, tool execution, API, DB, LLM prompts.

## Assets

- User research goals (may contain PII)
- API keys (LLM, search, LangSmith)
- Collected sources and snapshots
- Evidence graph integrity
- Infrastructure (DB, Redis, compute cost)

## Threat catalog

| ID | Threat | Vector | Impact | Mitigation |
|---|---|---|---|---|
| T1 | SSRF | malicious URL | internal network scan | DNS+IP validation, block private ranges |
| T2 | DNS rebinding | TTL flip | SSRF bypass | pin IP for request |
| T3 | Redirect abuse | 302 chain | SSRF | re-validate each hop |
| T4 | Prompt injection | page content | tool misuse | DATA blocks, phase tool allowlists |
| T5 | Tool injection | tampered tool output | wrong actions | schema validation, no eval |
| T6 | Malicious HTML/files | XSS, parser bugs | user harm | sanitize, MIME allowlist, size caps |
| T7 | Decompression bomb | gzip bomb | DoS | byte limits |
| T8 | Path traversal | upload filename | FS escape | UUID storage keys |
| T9 | Secret exfiltration | prompt trick | key leak | never inject secrets; log redaction |
| T10 | XSS | report in UI | account compromise | CSP, React escaping |
| T11 | SQL injection | API params | DB breach | SQLAlchemy ORM only |
| T12 | Rate abuse | spam runs | DoS / cost | Redis rate limits |
| T13 | Denial-of-wallet | infinite loop | API cost | ResearchBudget hard stops |
| T14 | PII in logs | verbose logging | compliance | redaction middleware |
| T15 | Supply chain | bad dependency | breach | Dependabot, audit in CI |

## Trust boundaries

```text
[User] → [Web UI] → [API] → [Orchestrator] → [Tools/Fetch] → [Internet]
                              ↓
                         [PostgreSQL]
```

Untrusted: Internet content, uploaded files, LLM outputs before verification.

## Implementation phases

| Control | Phase |
|---|---|
| Threat model doc | 0.5 ✓ |
| Secure fetch pipeline | 4 |
| Rate limiting | 6 |
| Full security hardening | 9 |

## Content rule

> Retrieved content is DATA, never trusted instruction.
