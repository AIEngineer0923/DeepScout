# ADR 012: Final Research Quality Architecture

## Status

Accepted; amended (2026-08-23)

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
8. **Material completeness gate** — coverage is requirement-scoped and evidence-backed. Central
   partial/unsupported requirements prevent `PASS`; a globally searched run, incidental number, or
   unrelated comparison cannot satisfy them.
9. **Requirement-aware evidence** — source class and conservative evidence type metadata are kept
   distinct from relevance. Quantitative and comparison requirements need attributable support of
   the requested kind.
10. **Canonical mode profiles** — Quick/Standard/Deep share completion truthfulness while increasing
    bounded task/query/correction/rewrite depth. Each mode reserves iteration/source capacity for
    correction and separately caps cumulative embedding tokens.
11. **Canonical bibliography** — the renderer removes model-emitted EN/IT bibliography sections and
    appends one localized list from cited evidence.

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

Coverage diagnoses the observable pipeline stage but cannot prove that external evidence does not
exist. After bounded unsuccessful attempts it may publish an explicit partial/blocked report; it
must not translate retrieval failure into a claim of literature non-existence.

## Benchmark

Dataset: `libs/evaluation/data/final_report_quality_v1.json`  
Live runner: `scripts/final_report_quality_live.py`
Structural corpus: `libs/evaluation/data/research_completeness_regressions_v1.json`
CI manifest gate: `scripts/research_completeness_gate.py`
