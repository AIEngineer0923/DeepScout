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

Persist experience in PostgreSQL (migration `014`):

- `learning_cases`
- `improvement_candidates`
- `learning_policy_versions`

Retrieval regression framework remains a **specialized input** — corpora and ingest paths unchanged.

## Runtime hook (bounded)

Promoted global policy may add **at most +1** `gap_queries_per_round_bonus` for corrective research (`policy_runtime.py`). No retrieval weight mutation, no prompt rewriting, no autonomous deploy.

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

`scripts/learning_loop_gate.py` proves the full deterministic loop on `learning_loop_deterministic_v1.json` (zero provider spend).

## Consequences

- Operators gain tenant-scoped learning case storage and policy versioning APIs
- Hosted `/ready` expects Alembic head `014`
- Human approval remains required for high-impact candidates
- Statistical significance is not claimed on tiny samples — honest `INCONCLUSIVE` default
