# ADR-009: Run-scoped compiled knowledge (LLM Wiki adaptation)

**Status:** Accepted as optional derived layer  
**Date:** 2026-08-21  
**Depends on:** ADR-008 (hybrid retrieval)  
**Baseline main:** `d3b4884be6c4e6654a8c40c777934450b599ce0f`

## Context

Karpathy’s LLM Wiki pattern (2026 gist) compiles raw sources into a persistent interlinked wiki so agents do not re-derive knowledge on every query. DeepScout already has:

- immutable `SourceSnapshot` authority
- Claim / Evidence / Contradiction graph
- hybrid FTS + pgvector retrieval

A naive markdown vault wiki would create a second authority and enable persistent prompt injection. DeepScout therefore adapts the pattern as a **run-scoped, provenance-first compiled layer**.

## Decision

| Item | Decision |
|---|---|
| LLM_WIKI | **IMPLEMENTED_OPTIONAL** — deterministic compiler from claims with evidence; not the default evidence path |
| RAW vs COMPILED | Distinct corpora; planner `corpus` field (`raw` / `compiled` / `both`) |
| OBSIDIAN | **OPTIONAL_EXPORT** — Markdown/frontmatter export only; no runtime dependency |
| RELATIONAL_KNOWLEDGE_GRAPH | **IMPLEMENTED** via PostgreSQL FKs (`wiki_*`, `knowledge_relations`) |
| DEDICATED_GRAPH_DATABASE | **REJECTED** |
| GRAPHIFY_DEEPSCOUT_RUNTIME | **REJECT** (see `GRAPHIFY_EVALUATION.md`) |
| GRAPHIFY_MASTER_AGENT_OS | **DEFER** (private workflow only; never committed here) |

## Authority hierarchy

```text
Source → SourceSnapshot → Evidence → Claim → WikiStatement → WikiPage → report
```

A WikiStatement is **never** evidence. Missing `claim_id`/`evidence_id` is a lint failure.

## Compiler

v1 compiler is **deterministic**:

- CREATE/CONFIRM statements from claims that already have evidence
- revise page bodies with revision history
- skip claims without evidence
- idempotent rebuild

No free-form LLM self-modification of the knowledge base in v1.

## Security

Compiled text is UNTRUSTED DATA. Persistent injection strings may be stored verbatim as statements but cannot grant tools, change budgets, or become verified evidence without snapshot-backed quotes.

## Benchmark (2026-08-21, seeded corpus)

| Mode | Phrase recall |
|---|---|
| RAW_RAG_ONLY | 0.833 |
| COMPILED_ONLY | 1.000 |
| COMPILED_PLUS_RAW | 0.833 |

Interpretation: compiled statements help “what have we learned?” style lookups on this tiny run-scoped corpus. Mixing compiled+raw does not beat raw overall here (no-answer / adversarial cases still surface raw hits). Hybrid RAG remains the default evidence path. Wiki stays **optional / derived**.

## Consequences

- Hybrid RAG remains the default for passage lookup and citation.
- Compiled knowledge helps “what have we learned?” navigation inside a run.
- Global shared knowledge bases remain out of scope (MODE A run isolation).
