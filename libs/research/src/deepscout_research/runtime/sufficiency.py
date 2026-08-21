"""Research sufficiency — informs stopping; does not override deterministic termination."""

from __future__ import annotations

from dataclasses import dataclass

from deepscout_core.domain.enums import SufficiencyAction
from deepscout_core.domain.schemas import ResearchTaskRead

from deepscout_research.workers.pool import WorkerResult


@dataclass(frozen=True, slots=True)
class SufficiencyDecision:
    action: SufficiencyAction
    reason: str
    new_sources: int
    completed_tasks: int


def evaluate_sufficiency(
    *,
    tasks: list[ResearchTaskRead],
    batch: list[WorkerResult],
    remaining_iterations: int,
    evidence_count: int,
) -> SufficiencyDecision:
    new_sources = sum(item.sources_added for item in batch)
    completed = sum(1 for task in tasks if task.status.value == "completed")
    failed = sum(1 for task in tasks if task.status.value == "failed")
    pending = sum(1 for task in tasks if task.status.value in {"pending", "ready", "running"})
    if pending == 0 and completed > 0:
        return SufficiencyDecision(
            SufficiencyAction.FINALIZE,
            "no_pending_work",
            new_sources,
            completed,
        )
    if new_sources == 0 and completed > 0 and remaining_iterations <= 1:
        return SufficiencyDecision(
            SufficiencyAction.FINALIZE,
            "low_marginal_yield",
            new_sources,
            completed,
        )
    if failed > 0 and pending > 0 and evidence_count == 0:
        return SufficiencyDecision(
            SufficiencyAction.TARGET_SPECIFIC_GAP,
            "failures_without_evidence",
            new_sources,
            completed,
        )
    if pending > 0 and remaining_iterations > 0:
        return SufficiencyDecision(
            SufficiencyAction.CONTINUE,
            "work_remaining",
            new_sources,
            completed,
        )
    return SufficiencyDecision(
        SufficiencyAction.FINALIZE,
        "default_finalize",
        new_sources,
        completed,
    )
