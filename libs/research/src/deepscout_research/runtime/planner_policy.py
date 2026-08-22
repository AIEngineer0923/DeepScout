"""Apply bounded planner learning policy to planner output."""

from __future__ import annotations

from deepscout_core.domain.enums import PlanDecomposition
from deepscout_core.domain.schemas import PlannerOutput

ABSOLUTE_MAX_PLANNER_TASKS = 10


def apply_planner_runtime_policy(
    output: PlannerOutput,
    *,
    max_tasks_bonus: int = 0,
    decomposition_strictness: float = 0.5,
    max_validator_tasks: int = 8,
) -> tuple[PlannerOutput, int]:
    """Bounded planner hooks — no autonomous goal mutation."""
    strictness = min(1.0, max(0.0, decomposition_strictness))
    tasks = list(output.tasks)
    decomposition = output.decomposition
    if strictness >= 0.65 and decomposition == PlanDecomposition.SIMPLE and len(tasks) >= 2:
        decomposition = PlanDecomposition.CHAIN
    effective_cap = min(ABSOLUTE_MAX_PLANNER_TASKS, max_validator_tasks + max(0, max_tasks_bonus))
    if len(tasks) > effective_cap:
        tasks = tasks[:effective_cap]
    return output.model_copy(update={"tasks": tasks, "decomposition": decomposition}), effective_cap
