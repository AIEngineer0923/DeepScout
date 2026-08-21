# ADR-014: Planner DAG quality and bounded plan repair

Status: Accepted  
Date: 2026-08-21

## Context

Live runs on main `6338faa` showed two planner defects:

1. Simple factual goals were split into two independent tasks (over-decomposition).
2. Multi-hop goals persisted `depends_on: []`; sequencing came from batch scheduling, not information flow.

Root cause: `PlannerOutput` emitted questions only. `planner_output_to_write` always called `merge_planner_tasks([], questions)`, so every task was independent. `PLANNER_V1` instructed “Emit 2-5 prioritized research questions.”

## Decision

- Keep `PLANNER_V1` retrievable for rollback (`PLANNER_PROMPT_VERSION=1`). It is not the default registry entry. `PromptStatus.DEPRECATED` is unused because `compose_system_message` refuses deprecated specs.
- Promote `PLANNER_V2` (`PLANNER_PROMPT_VERSION=2`) with a `decomposition` field and first-class `tasks` (`depends_on`, `completion_criteria`, `parallel_safe`).
- Apply one-shot deterministic `repair_plan` (merge duplicates, collapse `simple`, chain missing edges, mixed fan-in, drop cycles). No recursive replanning.
- Evaluate DAGs with deterministic checks (acyclic, no self-dep, unreachable, termination).

## Consequences

- Simple labelled goals repair to one task.
- Chain/mixed labelled goals get explicit `depends_on`.
- Legacy tests that omit `decomposition` keep question-only behavior (`unspecified`).
