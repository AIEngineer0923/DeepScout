"""Adaptive worker allocation — heuristic, not a scientific score."""

from __future__ import annotations

from dataclasses import dataclass

from deepscout_core.domain.enums import AllocationClass
from deepscout_core.domain.schemas import ResearchTaskRead
from deepscout_core.settings import Settings

from deepscout_research.tasks.graph import TaskGraph


@dataclass(frozen=True, slots=True)
class AllocationDecision:
    allocation_class: AllocationClass
    max_workers: int
    ready_count: int
    reason: str


def allocate_workers(
    tasks: list[ResearchTaskRead],
    *,
    settings: Settings,
    concurrency_limit: int,
    remaining_tool_calls: int,
    parallel_preference: float = 0.5,
) -> AllocationDecision:
    graph = TaskGraph(tuple(tasks))
    graph.validate_dependencies()
    ready = graph.ready_tasks()
    independent = [task for task in ready if not task.depends_on]
    n = len(ready)
    if remaining_tool_calls <= 0:
        return AllocationDecision(
            AllocationClass.SINGLE_AGENT,
            max_workers=0,
            ready_count=n,
            reason="no_tool_budget",
        )
    hard_cap = max(
        1,
        min(
            concurrency_limit,
            settings.agent_max_total_workers,
            remaining_tool_calls,
            n or 1,
        ),
    )
    if n <= 1:
        return AllocationDecision(
            AllocationClass.SEQUENTIAL_SINGLE if n == 1 else AllocationClass.SINGLE_AGENT,
            max_workers=1,
            ready_count=n,
            reason="one_or_zero_ready",
        )
  # Learning may bias toward sequential vs wider parallel within hard_cap.
    pref = min(1.0, max(0.0, parallel_preference))
    wide_threshold = 4 if pref >= 0.55 else 5
    sequential_bias = pref < 0.35

    if n <= 3 and len(independent) == n:
        workers = 1 if sequential_bias and n > 1 else min(hard_cap, n)
        alloc_class = (
            AllocationClass.SEQUENTIAL_SINGLE
            if workers == 1 and n > 1
            else AllocationClass.SMALL_PARALLEL
        )
        return AllocationDecision(
            alloc_class,
            max_workers=workers,
            ready_count=n,
            reason="few_independent_tasks",
        )
    if len(independent) >= wide_threshold:
        workers = 1 if sequential_bias else hard_cap
        return AllocationDecision(
            AllocationClass.SEQUENTIAL_SINGLE if workers == 1 else AllocationClass.WIDE_PARALLEL,
            max_workers=workers,
            ready_count=n,
            reason="wide_independent_fanout",
        )
    workers = 1 if sequential_bias else min(hard_cap, max(1, len(independent) or 1))
    alloc_class = (
        AllocationClass.SEQUENTIAL_SINGLE
        if workers == 1 and n > 1
        else AllocationClass.SMALL_PARALLEL
    )
    return AllocationDecision(
        alloc_class,
        max_workers=workers,
        ready_count=n,
        reason="mixed_dependencies",
    )
