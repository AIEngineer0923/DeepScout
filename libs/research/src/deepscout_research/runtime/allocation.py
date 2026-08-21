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
) -> AllocationDecision:
    graph = TaskGraph(tuple(tasks))
    graph.validate_dependencies()
    ready = graph.ready_tasks()
    independent = [task for task in ready if not task.depends_on]
    n = len(ready)
    hard_cap = max(
        1,
        min(
            concurrency_limit,
            settings.agent_max_total_workers,
            max(1, remaining_tool_calls),
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
    if n <= 3 and len(independent) == n:
        return AllocationDecision(
            AllocationClass.SMALL_PARALLEL,
            max_workers=min(hard_cap, n),
            ready_count=n,
            reason="few_independent_tasks",
        )
    if len(independent) >= 4:
        return AllocationDecision(
            AllocationClass.WIDE_PARALLEL,
            max_workers=hard_cap,
            ready_count=n,
            reason="wide_independent_fanout",
        )
    return AllocationDecision(
        AllocationClass.SMALL_PARALLEL,
        max_workers=min(hard_cap, max(1, len(independent) or 1)),
        ready_count=n,
        reason="mixed_dependencies",
    )
