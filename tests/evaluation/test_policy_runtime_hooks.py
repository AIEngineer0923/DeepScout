"""Runtime policy hook unit tests — deterministic, no provider spend."""

from __future__ import annotations

import uuid

from deepscout_core.domain.enums import PlanDecomposition, ResearchTaskStatus
from deepscout_core.domain.schemas import PlannerOutput, PlannerTask, ResearchTaskRead
from deepscout_core.settings import get_settings
from deepscout_evaluation.learning.policy import reasoning_effort_from_policy
from deepscout_evaluation.learning.policy_families import PolicyFamily
from deepscout_evaluation.learning.policy_runtime import (
    effective_query_strategy_params,
    policy_from_run_snapshot,
)
from deepscout_research.runtime.allocation import allocate_workers
from deepscout_research.runtime.planner_policy import apply_planner_runtime_policy
from deepscout_research.runtime.sufficiency import evaluate_sufficiency
from deepscout_research.workers.pool import WorkerResult


def test_query_strategy_params_from_snapshot() -> None:
    snapshot = {
        "learning_policies": {
            "learning_policy_versions": [],
            "effective": {
                family.value: {} for family in PolicyFamily
            },
        }
    }
    snapshot["learning_policies"]["effective"]["query_strategy"] = {
        "search_variant_count_delta": 1,
        "zero_yield_reformulation_bonus": 1,
    }
    effective = policy_from_run_snapshot(snapshot)
    params = effective_query_strategy_params(effective)
    assert params["search_variant_count_delta"] == 1
    assert params["zero_yield_reformulation_bonus"] == 1


def test_allocation_parallel_preference_biases_workers() -> None:
    settings = get_settings()
    tasks = [
        ResearchTaskRead(
            id=uuid.uuid4(),
            task_key=f"t{i}",
            objective=f"obj{i}",
            status=ResearchTaskStatus.READY,
            priority=i,
            depends_on=[],
            allowed_tools=["web_search"],
        )
        for i in range(4)
    ]
    sequential = allocate_workers(
        tasks,
        settings=settings,
        concurrency_limit=4,
        remaining_tool_calls=10,
        parallel_preference=0.1,
    )
    parallel = allocate_workers(
        tasks,
        settings=settings,
        concurrency_limit=4,
        remaining_tool_calls=10,
        parallel_preference=0.9,
    )
    assert sequential.max_workers <= parallel.max_workers


def test_sufficiency_policy_delta() -> None:
    tasks = [
        ResearchTaskRead(
            id=uuid.uuid4(),
            task_key="t1",
            objective="o",
            status=ResearchTaskStatus.COMPLETED,
            priority=1,
            depends_on=[],
            allowed_tools=["web_search"],
        )
    ]
    batch = [WorkerResult(uuid.uuid4(), uuid.uuid4(), success=True, sources_added=0)]
    early = evaluate_sufficiency(
        tasks=tasks,
        batch=batch,
        remaining_iterations=2,
        evidence_count=3,
        evidence_sufficiency_threshold_delta=0.1,
    )
    late = evaluate_sufficiency(
        tasks=tasks,
        batch=batch,
        remaining_iterations=2,
        evidence_count=1,
        evidence_sufficiency_threshold_delta=0.1,
    )
    assert early.reason == "evidence_sufficiency_met"
    assert late.reason != "evidence_sufficiency_met"


def test_reasoning_effort_mapping() -> None:
    assert reasoning_effort_from_policy({"reasoning_effort_level": 0}) is None
    assert reasoning_effort_from_policy({"reasoning_effort_level": 1}) == "low"
    assert reasoning_effort_from_policy({"reasoning_effort_level": 2}) == "medium"


def test_planner_strictness_upgrades_simple() -> None:
    output = PlannerOutput(
        decomposition=PlanDecomposition.SIMPLE,
        tasks=[
            PlannerTask(task_key="a", objective="one", question_text="one"),
            PlannerTask(task_key="b", objective="two", question_text="two"),
        ],
        questions=[],
        approach="test approach",
        success_criteria="test criteria",
    )
    adjusted, cap = apply_planner_runtime_policy(
        output, max_tasks_bonus=1, decomposition_strictness=0.8
    )
    assert adjusted.decomposition == PlanDecomposition.CHAIN
    assert cap >= 8
