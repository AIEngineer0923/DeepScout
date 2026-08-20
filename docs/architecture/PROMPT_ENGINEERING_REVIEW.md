# Prompt Engineering Review — August 2026

Status key: **IMPLEMENTED** = in registry/runtime; **IMPLEMENTED_NOT_LIVE_VERIFIED** = unit-tested only.

## global_policy (v1)

| Field | Value |
|-------|-------|
| ROLE | all |
| STATUS | IMPLEMENTED |
| MODEL COMPAT | google, openai, anthropic |
| RESPONSIBILITY | Shared invariants only |
| INPUT | n/a |
| OUTPUT | n/a |
| CONTEXT | Not used as runtime context |
| TOOLS | n/a |
| TRUST | Highest privileged layer |
| TERMINATION | n/a |
| STRUCTURED OUTPUT | n/a |
| FEW-SHOT | NO — invariants are explicit |
| CACHING | Stable prefix candidate |
| EVALS | prompt_injection, secret leakage |
| LANGSMITH | trace metadata only |
| SECURITY | indirect injection tests |

## planner (v1)

| Field | Value |
|-------|-------|
| STATUS | IMPLEMENTED_NOT_LIVE_VERIFIED |
| SCHEMA | PlannerOutput |
| TOOLS | none |
| CONTEXT | goal + budget summary only |
| TERMINATION | single structured plan |
| FEW-SHOT | NO — schema + contracts sufficient |
| EVALS | plan_adherence, task_decomposition |

## research_worker (v1)

| Field | Value |
|-------|-------|
| STATUS | IMPLEMENTED |
| SCHEMA | WorkerResult (graph state) |
| TOOLS | web_search allowlist |
| CONTEXT | single task slice |
| TERMINATION | bounded LangGraph loop |
| EVALS | worker_task_adherence, tool_selection |

## extractor / verifier / critic / synthesis / report (v1)

Each follows the same pattern: minimal role instructions, typed output contracts, no network tools except worker, deterministic phases preferred over LLM where possible (extract/verify/critic deterministic today; synthesis/report LLM or deterministic mix).

| prompt_id | LLM LIVE | DETERMINISTIC PATH |
|-----------|----------|-------------------|
| extractor | CANDIDATE | extract.py deterministic |
| verifier | CANDIDATE | verify.py deterministic |
| critic | IMPLEMENTED | critic.py deterministic gate |
| synthesis | IMPLEMENTED_NOT_LIVE_VERIFIED | ModelRouter + SynthesisOutput |
| report | IMPLEMENTED | report.py deterministic markdown |

## Change process

All prompts: `prompt_id` + `prompt_version` + `prompt_status` in LangSmith metadata via `PromptSpec.trace_metadata()` and `langsmith_metadata()`.

Promotion requires LangSmith experiment against `deepscout-baseline-v1` (see `scripts/langsmith_bootstrap.py`).
