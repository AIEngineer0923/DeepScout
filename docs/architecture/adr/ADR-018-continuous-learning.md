# ADR-018: Controlled Continuous Learning Loop

**Status:** Accepted  
**Date:** 2026-08-22

## Context

DeepScout already had:

- Per-run deterministic evaluation (`evaluation_results`)
- Retrieval regression corpora with human-reviewed promotion (PR #58/#59)
- Bounded same-run adaptation (corrective research, critics, HITL)
- Explicit **no auto-learning** policy in docs

The gap was a **system-wide, auditable loop** from production observation → diagnosis → candidate → experiment → promotion → versioned policy — without autonomous code mutation or uncontrolled production experiments.

## Decision

Extend `libs/evaluation` with a **thin learning module** (not a separate microservice):

| Component | Role |
|-----------|------|
| `learning/models.py` | `LearningCase`, `ImprovementCandidate`, `PolicyVersion` |
| `learning/failure_taxonomy.py` | System-wide `FailureClass` extending `RetrievalFailureClass` |
| `learning/observation.py` | Observe terminal eval failures (skip public demos) |
| `learning/diagnosis.py` | Earliest defensible root cause |
| `learning/candidates.py` | Typed improvement candidates |
| `learning/experiment.py` | Deterministic baseline vs candidate (no provider calls) |
| `learning/promotion.py` | Pareto-aware promotion verdict |
| `learning/policy.py` | Versioned policy bundles + rollback |
| `learning/experience_store.py` | Tenant-scoped persistence adapter |
| `learning/trust.py` | Trust levels + poisoning defenses |

Persist experience in PostgreSQL (migrations `014`–`016`):

- `learning_cases`
- `improvement_candidates`
- `learning_policy_versions`
- `learning_experience_samples`, `learning_policy_monitoring`, `learning_experiment_jobs`, `learning_audit_events` (016)

Retrieval regression framework remains a **specialized input** — corpora and ingest paths unchanged.

## Runtime hooks (bounded)

Promoted policies may adjust bounded runtime knobs per family via `policy_resolver.py` and `policy_runtime.py`. Nine families are runtime-wired (migration `016`):

| Family | Example knob | Hook |
|--------|--------------|------|
| `corrective_research` | `gap_queries_per_round_bonus` (+1 max) | `corrective_research.py` |
| `retrieval` | `retrieval_candidate_k_multiplier`, `retrieval_top_k_delta` | `phases/extract.py` |
| `query_strategy` | `search_variant_count_delta`, `zero_yield_reformulation_bonus` | `workers/pool.py` |
| `allocation` | `allocation_parallel_preference` | `runtime/allocation.py` |
| `sufficiency` | threshold deltas | `runtime/sufficiency.py` |
| `synthesis` | `report_rewrite_bonus` (+1 max) | `orchestrator.py` |
| `reasoning` | `reasoning_effort_level` | `routing/model_router.py` |
| `planner` | `max_tasks_bonus`, `planner_decomposition_strictness` | `planner_policy.py` |
| `cost_latency` | `prefer_lower_cost_strategy` | model routing |

Hard bounds in `policy_families.HARD_BOUNDS` — learning cannot exceed application envelopes. Adaptive policies **cannot** override authentication, tenant isolation, SSRF, tool allowlists, evidence provenance, HITL authority, or absolute budget ceilings.

Post-promotion: monitoring windows, anti-oscillation cooldown, bounded auto-rollback for low-risk families, manual/HITL rollback for medium/high risk. User feedback is an untrusted observation signal; HITL review events are authoritative but neither auto-overrides security policy.

See [CONTINUOUS_LEARNING.md](../CONTINUOUS_LEARNING.md) for diagrams and effective-runtime-policy precedence.

## What we explicitly reject

- Autonomous source-code mutation or PR creation
- Cross-tenant global learning from private content
- Online fine-tuning or RL infrastructure
- Auto-promotion of `production_candidate` fixtures to CI
- LangSmith as source of truth for deterministic invariants

## Trust ladder

```
UNTRUSTED_OBSERVATION → SANITIZED_CANDIDATE → REVIEWED_CASE → VALIDATED_LEARNING → PROMOTED_POLICY
```

External web content and raw user feedback never skip review.

## CI

- `scripts/learning_loop_gate.py` — full deterministic loop on `learning_loop_deterministic_v1.json`
- `scripts/learning_effectiveness_gate.py` — before/after cohort analytics semantics (zero provider spend)

## Consequences

- Operators gain tenant-scoped learning case storage, policy versioning APIs, and `/learning` UI (hosted)
- Hosted `/ready` expects Alembic head `017`
- Human approval remains required for high-impact candidates
- Statistical significance is not claimed on tiny samples — honest `INCONCLUSIVE` default
