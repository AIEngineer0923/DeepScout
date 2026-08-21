# LangSmith privacy operating model

LangSmith is **optional operator observability**, not a required product backend.

## Default

`LANGSMITH_TRACING` defaults to **false**.

Tracing is opt-in. DeepScout does not assume consent to send research content to a third party.

## What is transmitted when tracing is on

| Class | Transmitted? |
|---|---|
| Provider API keys, DB URLs, Redis URLs, passwords, tokens | **No** — `redact_trace_inputs` strips known secret keys and settings blobs |
| Research goals | **Yes** — may contain sensitive operator content |
| Retrieved page text / snippets | **Yes** — untrusted third-party content |
| Model prompts and completions | **Yes** — includes untrusted DATA blocks |
| Claims, evidence quotes, report markdown | **Yes** if those objects appear in traced inputs/outputs |
| Evaluation traces | **Yes** when evaluators run under LangSmith |

Secrets must never be transmitted. Research content is not a secret, but it **is** potentially confidential.

## Operator contract

1. Leave tracing off unless you intend LangSmith to store this run's research text.
2. If tracing is on, treat the LangSmith project as a sensitive data store (retention, region, access).
3. Use `LANGSMITH_ENDPOINT` for the correct region (for example EU).
4. Do not put secrets in goals, notes, or fetched pages and expect redaction to catch them. Redaction is key-name based, not a DLP scanner.

## Process environment

`configure_observability` / `configure_langsmith_env` set `LANGSMITH_TRACING` to `true` or `false` explicitly so a leftover shell variable cannot keep tracing enabled after settings say off.
