"""Bounded, application-owned plan repair. No recursive replanning."""

from __future__ import annotations

import re
from uuid import uuid4

from deepscout_core.domain.enums import PlanDecomposition, ResearchTaskStatus
from deepscout_core.domain.schemas import (
    PlannerOutput,
    PlannerQuestion,
    PlannerTask,
    ResearchTaskRead,
)

from deepscout_research.tasks.graph import TaskGraph, TaskGraphError, merge_planner_tasks

_WS = re.compile(r"\s+")


def _norm_objective(text: str) -> str:
    return _WS.sub(" ", text.strip().lower())


def _as_read(tasks: list[PlannerTask]) -> list[ResearchTaskRead]:
    return [
        ResearchTaskRead(
            id=uuid4(),
            task_key=task.task_key,
            objective=task.objective,
            status=ResearchTaskStatus.PENDING,
            priority=task.priority,
            depends_on=list(task.depends_on),
            allowed_tools=list(task.allowed_tools),
        )
        for task in tasks
    ]


def _drop_unknown_and_self_deps(tasks: list[PlannerTask]) -> list[PlannerTask]:
    keys = {task.task_key for task in tasks}
    repaired: list[PlannerTask] = []
    for task in tasks:
        deps = [dep for dep in task.depends_on if dep in keys and dep != task.task_key]
        repaired.append(task.model_copy(update={"depends_on": deps}))
    return repaired


def _break_cycles(tasks: list[PlannerTask]) -> list[PlannerTask]:
    current = list(tasks)
    for _ in range(len(current) + 1):
        try:
            TaskGraph(tuple(_as_read(current))).validate_dependencies()
            return current
        except TaskGraphError:
            # Drop the last extra edge on the highest-priority cyclic node.
            by_key = {task.task_key: task for task in current}
            changed = False
            for task in sorted(current, key=lambda item: item.priority, reverse=True):
                if task.depends_on:
                    by_key[task.task_key] = task.model_copy(update={"depends_on": task.depends_on[:-1]})
                    current = list(by_key.values())
                    changed = True
                    break
            if not changed:
                return [task.model_copy(update={"depends_on": []}) for task in current]
    return [task.model_copy(update={"depends_on": []}) for task in current]


def _dedupe_objectives(tasks: list[PlannerTask]) -> list[PlannerTask]:
    seen: set[str] = set()
    unique: list[PlannerTask] = []
    dropped_keys: set[str] = set()
    for task in tasks:
        key = _norm_objective(task.objective)
        if key in seen:
            dropped_keys.add(task.task_key)
            continue
        seen.add(key)
        unique.append(task)
    if not dropped_keys:
        return unique
    return [
        task.model_copy(update={"depends_on": [dep for dep in task.depends_on if dep not in dropped_keys]})
        for task in unique
    ]


def _chain_by_priority(tasks: list[PlannerTask]) -> list[PlannerTask]:
    ordered = sorted(tasks, key=lambda item: (item.priority, item.task_key))
    chained: list[PlannerTask] = []
    previous: str | None = None
    for task in ordered:
        chained.append(task.model_copy(update={"depends_on": [previous] if previous else []}))
        previous = task.task_key
    return chained


def _ensure_keys(tasks: list[PlannerTask]) -> list[PlannerTask]:
    used: set[str] = set()
    out: list[PlannerTask] = []
    for index, task in enumerate(tasks, start=1):
        key = task.task_key if task.task_key not in used else f"t{index}"
        used.add(key)
        question = task.question_text or task.objective
        out.append(task.model_copy(update={"task_key": key, "question_text": question}))
    return out


def repair_plan(output: PlannerOutput) -> PlannerOutput:
    """One-shot structural repair. Does not call the planner again."""
    questions = [item.text for item in sorted(output.questions, key=lambda item: item.priority)]
    tasks = merge_planner_tasks(list(output.tasks), questions)
    tasks = _ensure_keys(tasks)
    tasks = _dedupe_objectives(tasks)
    tasks = _drop_unknown_and_self_deps(tasks)

    decomposition = output.decomposition
    if decomposition == PlanDecomposition.SIMPLE:
        primary = sorted(tasks, key=lambda item: (item.priority, item.task_key))[:1]
        tasks = [task.model_copy(update={"depends_on": [], "parallel_safe": True}) for task in primary]
    elif decomposition == PlanDecomposition.PARALLEL:
        tasks = [task.model_copy(update={"depends_on": [], "parallel_safe": True}) for task in tasks]
    elif decomposition == PlanDecomposition.CHAIN:
        if len(tasks) >= 2 and not any(task.depends_on for task in tasks):
            tasks = _chain_by_priority(tasks)
        tasks = [task.model_copy(update={"parallel_safe": not bool(task.depends_on)}) for task in tasks]
    elif decomposition == PlanDecomposition.MIXED:
        if len(tasks) >= 3 and not any(task.depends_on for task in tasks):
            ordered = sorted(tasks, key=lambda item: (item.priority, item.task_key))
            fan_in = ordered[-1]
            fan_out_keys = [task.task_key for task in ordered[:-1]]
            tasks = [
                *[task.model_copy(update={"depends_on": [], "parallel_safe": True}) for task in ordered[:-1]],
                fan_in.model_copy(update={"depends_on": fan_out_keys, "parallel_safe": False}),
            ]
        else:
            roots = {task.task_key for task in tasks if not task.depends_on}
            tasks = [
                task.model_copy(update={"parallel_safe": not task.depends_on or all(dep in roots for dep in task.depends_on)})
                for task in tasks
            ]

    tasks = _break_cycles(_drop_unknown_and_self_deps(tasks))
    questions_out = [
        PlannerQuestion(text=task.question_text or task.objective, priority=task.priority) for task in tasks
    ]
    return output.model_copy(update={"tasks": tasks, "questions": questions_out})
