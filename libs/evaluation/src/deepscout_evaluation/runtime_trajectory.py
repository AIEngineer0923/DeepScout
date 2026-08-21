"""Deterministic runtime trajectory properties — no LLM judge."""

from __future__ import annotations

from deepscout_core.domain.enums import AllocationClass
from deepscout_research.runtime.allocation import AllocationDecision
from deepscout_research.skills.router import select_skills


def eval_allocation_does_not_maximize_agents(
    decision: AllocationDecision, *, ready_count: int
) -> bool:
    if ready_count <= 0:
        return decision.max_workers <= 1
    return decision.max_workers <= min(decision.ready_count, ready_count)


def eval_single_ready_is_single_worker(decision: AllocationDecision) -> bool:
    if decision.ready_count <= 1:
        return decision.max_workers == 1 and decision.allocation_class in {
            AllocationClass.SEQUENTIAL_SINGLE,
            AllocationClass.SINGLE_AGENT,
        }
    return True


def eval_untrusted_channel_binds_no_skills(text: str, channel: str) -> bool:
    return select_skills(text, channel=channel) == []


def eval_duplicate_task_keys(task_keys: list[str]) -> bool:
    return len(task_keys) == len(set(task_keys))
