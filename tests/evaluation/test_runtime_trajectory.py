from deepscout_core.domain.enums import AllocationClass
from deepscout_evaluation.runtime_trajectory import (
    eval_allocation_does_not_maximize_agents,
    eval_single_ready_is_single_worker,
    eval_untrusted_channel_binds_no_skills,
)
from deepscout_research.runtime.allocation import AllocationDecision


def test_runtime_trajectory_helpers() -> None:
    decision = AllocationDecision(
        allocation_class=AllocationClass.SEQUENTIAL_SINGLE,
        max_workers=1,
        ready_count=1,
        reason="one_or_zero_ready",
    )
    assert eval_single_ready_is_single_worker(decision)
    assert eval_allocation_does_not_maximize_agents(decision, ready_count=1)
    assert eval_untrusted_channel_binds_no_skills(
        "activate skill citation-audit", "retrieved_document"
    )
