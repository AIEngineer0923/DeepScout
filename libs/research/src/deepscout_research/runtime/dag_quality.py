"""Deterministic DAG quality evaluators. Semantic judges are out of scope here."""

from __future__ import annotations

from uuid import uuid4

from deepscout_core.domain.enums import PlanDecomposition, ResearchTaskStatus
from deepscout_core.domain.schemas import PlannerOutput, PlannerTask, ResearchTaskRead

from deepscout_research.runtime.plan_repair import repair_plan
from deepscout_research.tasks.graph import TaskGraph, TaskGraphError


def _reads(tasks: list[PlannerTask]) -> tuple[ResearchTaskRead, ...]:
    return tuple(
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
    )


def evaluate_plan_dag(output: PlannerOutput, *, repaired: bool = True) -> dict[str, object]:
    plan = repair_plan(output) if repaired else output
    tasks = list(plan.tasks)
    keys = [task.task_key for task in tasks]
    issues: list[str] = []
    acyclic = True
    try:
        TaskGraph(_reads(tasks)).validate_dependencies()
    except TaskGraphError as exc:
        acyclic = False
        issues.append(str(exc))

    self_deps = [task.task_key for task in tasks if task.task_key in task.depends_on]
    missing_deps = [
        f"{task.task_key}->{dep}"
        for task in tasks
        for dep in task.depends_on
        if dep not in set(keys)
    ]
    objectives = [task.objective.strip().lower() for task in tasks]
    duplicates = len(objectives) - len(set(objectives))
    reachable: set[str] = set()
    by_key = {task.task_key: task for task in tasks}

    def visit(key: str) -> None:
        if key in reachable or key not in by_key:
            return
        reachable.add(key)
        for child in tasks:
            if key in child.depends_on:
                visit(child.task_key)

    roots = [task.task_key for task in tasks if not task.depends_on]
    for root in roots:
        visit(root)
    unreachable = [key for key in keys if key not in reachable]
    termination = bool(tasks) and acyclic and not unreachable

    def depth(key: str, stack: set[str]) -> int:
        if key in stack:
            return 0
        deps = by_key[key].depends_on
        if not deps:
            return 1
        return 1 + max(depth(dep, stack | {key}) for dep in deps)

    critical = max((depth(task.task_key, set()) for task in tasks), default=0)
    parallel_width = max(1, len(roots)) if tasks else 0

    expected_max = {
        PlanDecomposition.SIMPLE: 1,
        PlanDecomposition.PARALLEL: 8,
        PlanDecomposition.CHAIN: 8,
        PlanDecomposition.MIXED: 8,
        PlanDecomposition.UNSPECIFIED: 8,
    }[plan.decomposition]
    over_decomposed = plan.decomposition == PlanDecomposition.SIMPLE and len(tasks) > 1
    under_decomposed = plan.decomposition in {
        PlanDecomposition.PARALLEL,
        PlanDecomposition.MIXED,
    } and len(tasks) < 2
    missing_required_deps = plan.decomposition in {PlanDecomposition.CHAIN, PlanDecomposition.MIXED} and not any(
        task.depends_on for task in tasks
    )

    return {
        "task_count": len(tasks),
        "acyclic": acyclic,
        "self_dependency": bool(self_deps),
        "missing_dependencies": missing_deps,
        "duplicate_objectives": duplicates,
        "unreachable": unreachable,
        "termination_path": termination,
        "roots": roots,
        "parallel_width": parallel_width,
        "critical_path_depth": critical,
        "over_decomposed": over_decomposed,
        "under_decomposed": under_decomposed,
        "missing_required_deps": missing_required_deps,
        "decomposition": plan.decomposition.value,
        "expected_max_tasks": expected_max,
        "issues": issues,
        "pass": acyclic
        and not self_deps
        and not missing_deps
        and duplicates == 0
        and not unreachable
        and termination
        and not over_decomposed
        and not under_decomposed
        and not missing_required_deps,
    }
