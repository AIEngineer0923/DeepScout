"""Bounded global replan — DAG patch, not whole-plan rewrite."""

from __future__ import annotations

from dataclasses import dataclass

from deepscout_core.domain.schemas import PlannerTask, ResearchTaskRead
from deepscout_core.settings import Settings


@dataclass(frozen=True, slots=True)
class ReplanDecision:
    apply: bool
    new_tasks: tuple[PlannerTask, ...]
    reason: str


def evaluate_replan(
    *,
    settings: Settings,
    replans_used: int,
    tasks: list[ResearchTaskRead],
    last_batch_sources: int,
    evidence_count: int,
) -> ReplanDecision:
    if replans_used >= settings.agent_max_replans:
        return ReplanDecision(False, (), "max_replans")
    failed = [task for task in tasks if task.status.value == "failed"]
    pending = [task for task in tasks if task.status.value in {"pending", "ready", "running"}]
    if pending:
        return ReplanDecision(False, (), "work_still_pending")
    if not failed or last_batch_sources > 0:
        return ReplanDecision(False, (), "no_gap_signal")
    if evidence_count > 0 and len(failed) == 0:
        return ReplanDecision(False, (), "already_covered")
    existing_keys = {task.task_key for task in tasks}
    existing_objectives = {task.objective.strip().casefold() for task in tasks}
    existing = existing_keys | existing_objectives
    additions: list[PlannerTask] = []
    for index, task in enumerate(failed[: settings.agent_max_new_tasks_per_replan]):
        key = f"replan_{replans_used + 1}_{index + 1}"
        objective = f"Fill evidence gap for: {task.objective[:180]}"
        if key in existing or objective.casefold() in existing:
            continue
        additions.append(
            PlannerTask(
                task_key=key,
                objective=objective,
                question_text=task.objective,
                depends_on=[],
                priority=min(5, task.priority + 1),
            )
        )
    if not additions:
        return ReplanDecision(False, (), "duplicate_or_empty")
    return ReplanDecision(True, tuple(additions), "failed_tasks_need_gap_fill")
