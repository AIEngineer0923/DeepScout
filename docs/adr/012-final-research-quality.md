# ADR 012: Final Research Quality Architecture

## Status

Accepted (2026-08-22)

## Context

DeepScout could complete substantial research yet publish final reports that:

- leaked planner task text into user-facing output;
- listed all discovered sources instead of cited sources;
- ignored hard source constraints (`ONLY official EU`);
- declared global `INSUFFICIENT_EVIDENCE` when partial answers were supportable;
- stopped research on `low_marginal_yield` without requirement coverage;
- used deterministic concatenation instead of goal-conditioned synthesis.

## Decision

Introduce an application-owned quality architecture:

1. **ResearchContract / ReportContract** — structured user intent and deliverable shape, persisted in `config_snapshot`.
2. **Source admission** — discovered ≠ admissible ≠ evidence ≠ cited. Hard `ONLY` constraints fail closed.
3. **Requirement coverage** — per-requirement status including `SEARCHED_NO_EVIDENCE`, `PARTIAL`, `SUPPORTED`.
4. **Bounded corrective research** — gap tasks appended to existing `ResearchTask` graph (`RESEARCH_MAX_COVERAGE_ROUNDS`, `RESEARCH_MAX_GAP_QUERIES_PER_ROUND`).
5. **Goal-conditioned LLM report synthesis** — curated verified claims/evidence + contracts; LLM writes prose; app owns verification and policy.
6. **Final answer critic** — typed verdicts (`PASS`, `REVISION_REQUIRED`, `RESEARCH_GAP`, `BLOCKED_BY_EVIDENCE`) with bounded rewrites (`RESEARCH_MAX_REPORT_REWRITES`).
7. **Report revision metadata** — prior report bodies archived in `config_snapshot.report_revisions`; `save_report` upserts.

Rejected alternatives:

- New agent framework (CrewAI/AutoGen) — unnecessary; existing orchestrator sufficient.
- Global quality percentage — replaced with per-dimension evaluators.
- Hardcoded regression answers — forbidden; evaluation uses structural gates only.

## Consequences

- Orchestrator pipeline: research → evidence → corrective loops → finalize → report critic rewrites.
- Additional token cost on complex runs; simple factual runs skip corrective loops when supported.
- Live quality validation required before merge; unit tests alone insufficient.

## Pipeline (final)

```
user goal
  → ResearchContract + ReportContract
  → plan (+ contract research tasks: temporal, office-holder, dependent guidance)
  → authoritative discovery + source admission
  → fetch / index / extract / verify
  → structured domain propositions (TemporalClaim, VerifiedEntity, LegalReference)
  → requirement coverage
  → bounded corrective research (gap queries; HITL may pause budget extension)
  → contradiction → final critic → goal-conditioned synthesis → report
  → presentation (EN/IT) → publication / export
```

Reusable primitives (`TemporalClaim`, `LegalReference`, `CURRENT_OFFICE_HOLDER_LOOKUP`,
`dependency_gate`, primary legal follow-up) are domain-general research primitives — not
EU-specific answer hardcoding.

## Technical debt (non-blocking)

`RetrievalFailureClass` exists in contracts but full diagnostic wiring into coverage/critic
reason codes remains partial. Failures still surface primarily via `BLOCKED_BY_EVIDENCE` /
`MISSING_REQUIREMENT` critic codes until wiring is completed.

## Benchmark

Dataset: `libs/evaluation/data/final_report_quality_v1.json`  
Live runner: `scripts/final_report_quality_live.py`
