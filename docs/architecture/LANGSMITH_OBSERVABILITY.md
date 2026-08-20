# LangSmith Observability

## Environment

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<local only>
LANGSMITH_PROJECT=deepscout-dev
```

## Project auto-creation

LangSmith creates the project on first trace if it does not exist when
`LANGSMITH_PROJECT` is set. No separate UI step required for `deepscout-dev`.

## Trace hierarchy

```text
research_run (custom root)
├── phase:plan
├── phase:research
│   ├── tool:web_search
│   └── tool:fetch_url
├── phase:extract
├── phase:verify
├── phase:critic
└── phase:synthesis
```

## Metadata convention

```python
metadata = {
    "research_run_id": str(run_id),
    "phase": "extract_claims",
    "iteration": 2,
    "llm_provider": settings.llm_provider,
    "llm_model": resolved_model,
}
tags = ["deepscout", f"phase:{phase}", f"provider:{provider}"]
```

## Secrets policy

Never include in traces:

- API keys
- Raw `.env` values
- User PII from research goals (redact in logging middleware)

## Evaluations (Phase 9+)

| Evaluator | Metric |
|---|---|
| Citation correctness | evidence span ↔ snapshot |
| Evidence support | claims with valid quotes |
| Hallucination rate | unlinked claims / total |
| Tool success | tool failure ratio |
| Cost / latency | per phase p95 |

Implementation: `tests/evals/` + LangSmith datasets.

## Product boundary

LangSmith = operators/developers. Product UI = evidence graph + operational SSE events.
