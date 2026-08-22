# Evaluations

DeepScout records evaluation results per terminal research run in PostgreSQL (`evaluation_results`, migration `012`).

## When evaluations run

1. **At finalization** — orchestrator calls `persist_research_evaluations` when a run reaches a terminal status.
2. **On read (legacy backfill)** — if a terminal run has no rows yet, the API computes deterministic evaluators once, persists, and returns them. Second read uses stored rows only (no recompute).
3. **Operator backfill** — `scripts/backfill_evaluation_results.py` for bounded batch backfill (no provider calls).

Demo browsing reads persisted results only — zero provider spend.

## Registry

`libs/evaluation/src/deepscout_evaluation/registry.py` defines **48 evaluator slots** per run (version `1` today). Each spec has:

| Field | Meaning |
|-------|---------|
| `category` | UI grouping (e.g. retrieval, security, planning, quality) |
| `method` | `automated_check`, `hybrid_evaluation`, `llm_as_judge`, … |
| `applicability` | When the evaluator can run |

### Applicability labels

| Label | Meaning |
|-------|---------|
| `active_now` | Can run online with current run artifacts |
| `offline_only` | Requires offline workflow / LangSmith experiment |
| `not_applicable_by_design` | Wrong modality (e.g. image evaluator on text research) |
| `ground_truth_required` | Needs labeled references |
| `advanced_evaluation` | Optional deeper eval pipeline |

## Result statuses (UI)

| Status | Meaning |
|--------|---------|
| `passed` | Deterministic check succeeded |
| `failed` | Deterministic check failed |
| `score` | Numeric metric (e.g. duplicate retrieval rate) |
| `skipped` | Applicable but missing runtime artifact or policy skip |
| `unavailable` | Cannot run online (offline-only, missing ground truth, etc.) |
| `not_applicable` | Evaluator does not apply to this run type |
| `error` | Execution error |
| `pending` | Run not terminal yet |

The UI hides most `not_applicable_by_design` rows. Generic “not evaluated” is not shown when a precise status exists.

## What runs online today

Deterministic evaluators in `run_evals.py` include:

- Claim/evidence coverage, citation resolve rate, provenance
- Budget compliance, duplicate work, DAG validity
- Security scans (SSRF URLs, secret/PII patterns, prompt injection heuristics)
- Trajectory / phase adherence checks
- Retrieval isolation and duplicate candidate rate

## What does **not** run online (honest unavailable)

Examples:

- RAGAS faithfulness / context precision (optional import; offline)
- Recall@K, Precision@K, MRR without labeled chunks
- LLM-as-judge answer relevance (offline workflow)
- LangSmith-hosted code evaluators when not configured

Do not expect all 48 rows to show PASS — many correctly show **Unavailable** with a reason string.

## Retrieval quality benchmark (offline / live)

Repeatable suite for router intents, ablation, contextual comparison, compiled knowledge, and local graph retrieval:

```bash
# Router only — no DB, no provider keys
uv run python scripts/retrieval_quality_benchmark.py --router-only

# Full live benchmark — local Postgres + embedding provider
uv run python scripts/retrieval_quality_benchmark.py --live
```

Dataset: `libs/evaluation/data/retrieval_quality_benchmark_v2.json` (deterministic ground truth, not live-web dependent).

Legacy scripts still useful for focused checks:

- `scripts/retrieval_ablation_offline.py` — BM25 phrase-recall on v1.1 corpus
- `scripts/phase5_closure_gate.py` — dimension + hybrid ablation + pre-RAG vs RAG
- `scripts/compiled_knowledge_benchmark.py` — RAW vs COMPILED modes

## Persistence schema

Unique constraint: `(research_run_id, evaluator_id)`. Version changes create new semantics via `evaluator_version` column.

## API

Workspace payload includes `evaluations` array when run is terminal. Export endpoints follow the same persisted rows where implemented.

## For contributors

- Add evaluators in `registry.py` + computation in `run_evals.py` or dedicated module
- Map to matrix rows in `matrix.py`
- Tests: `tests/evaluation/`
- See [AGENTS.md](../AGENTS.md)
