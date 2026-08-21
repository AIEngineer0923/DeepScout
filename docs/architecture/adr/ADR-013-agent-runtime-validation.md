# ADR-013: Agent runtime final validation

Status: Accepted  
Date: 2026-08-21  
Baseline: `4e5f0da8815bb6963e0f946086236fa12142c33d` (ADR-012 merged)

## Problem

ADR-012 shipped a bounded agent runtime. This validation measured whether that
runtime works, which deferred items deserve promotion, and which defects to fix.

## Research (August 2026)

- Anthropic Agent Skills remain procedure (SKILL.md), not permission. Application
  logic must bind skills; retrieved/Wiki/tool text must not.
- Anthropic/OpenAI prompt cache hits are provider-reported
  (`cache_read_input_tokens`, nested `cached_tokens`). Do not infer hits.
- LangGraph time-travel (`get_state_history` / `update_state`) forks graph
  checkpoints. DeepScout product fork remains a new `ResearchRun`.
- OWASP Agentic Top 10 2026 (ASI01 goal hijack, ASI06 memory poisoning, ASI02
  tool misuse) reinforces DATA ≠ POLICY.

## Measured promotions

| Capability | Decision | Why |
|---|---|---|
| Prompt-cache instrumentation | **IMPLEMENTED_DEFAULT** | Parse provider cache-read fields; unknown stays None |
| Reasoning-effort kwargs | **IMPLEMENTED_OPTIONAL** | Capability allowlist; default unset; no universal param |
| Skill channel gating | **IMPLEMENTED_DEFAULT** | Only `task_objective` may bind skills |
| Worker context isolation | **IMPLEMENTED_DEFAULT** | `isolate_worker` no longer copies parent retrieved/working state |
| Privileged-tool authorization | **IMPLEMENTED_DEFAULT** | Unknown tools DENY; `web_search` ALLOW_AUTONOMOUS |
| Usage by role | **IMPLEMENTED_DEFAULT** | Attribute known tokens; missing stays None |
| Playwright runtime E2E | **IMPLEMENTED_DEFAULT** | Fixture suite: workers/skills/reviews/fork/history |
| Event-log replay | **IMPLEMENTED_OPTIONAL** | Reconstruct decisions; do not pretend web is deterministic |
| Live LangSmith runtime experiment | **IMPLEMENTED_OPTIONAL** | Script skips without credentials |

## Kept deferred / rejected

| Capability | Decision | Why |
|---|---|---|
| Hard `delegated_budget` | KEEP_DEFERRED | Global `FOR UPDATE` reservations cannot exceed the run cap (race-tested) |
| `max_depth` > 1 | KEEP_DEFERRED | DAG already parallelizes independent work; no measured nested-subagent win |
| LLM summarization compaction | KEEP_DEFERRED | Stub/LLM summaries drop snapshot refs; summaries must not become evidence |
| Finalization token carve-out | KEEP_DEFERRED | ADR-007 already finalizes after research tool/source exhaustion |
| Low-marginal-yield stop | IMPLEMENTED_DEFAULT already | Orchestrator already finalizes on sufficiency `low_marginal_yield` |
| Dynamic skill generation | KEEP_DEFERRED | Candidate lifecycle only; auto-promote **REJECT** |
| Semantic skill judges | KEEP_DEFERRED | Keyword router is sufficient and safer |
| Online eval → dataset | KEEP_DEFERRED | Privacy: do not auto-promote user runs |
| LangGraph time-travel UI | KEEP_DEFERRED | Domain fork is the product path |
| Generic cross-run memory | **REJECT** | Wiki/evidence/run state already persist knowledge |
| Semantic answer cache | **REJECT** | Isolation/poisoning risk without measured gain |

## Defects fixed in this validation

1. Untrusted text containing a builtin skill slug could bind that skill if passed
   to `select_skills`. Binding now requires `channel="task_objective"`.
2. `isolate_worker` copied parent retrieved blobs and working memory.
3. Anthropic/OpenAI cache-read fields were ignored.

## Non-goals

Do not reimplement ADR-011, ADR-012, Phase 5 RAG, or compiled Wiki.
