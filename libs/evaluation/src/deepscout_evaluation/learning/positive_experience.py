"""Positive experience learning — aggregate successful runs into optimization signals."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_persistence.store import ResearchStore

from deepscout_evaluation.learning.failure_taxonomy import FailureClass
from deepscout_evaluation.learning.models import (
    LearningCase,
    LearningCaseReviewState,
    LearningSubsystem,
    TrustLevel,
)
from deepscout_evaluation.learning.observation import observe_opportunity_from_metrics
from deepscout_evaluation.regression_origins import RegressionOrigin

MIN_POSITIVE_SAMPLES = 5
QUALITY_PASS_THRESHOLD = 0.8


def _quality_score(evaluation_rows: list[dict[str, Any]]) -> float:
    if not evaluation_rows:
        return 0.0
    passed = sum(1 for row in evaluation_rows if str(row.get("status")) == "passed")
    return passed / len(evaluation_rows)


def _cost_proxy(evaluation_rows: list[dict[str, Any]], consumption: dict[str, Any] | None) -> float:
    if consumption:
        return float(consumption.get("tool_calls", 0) + consumption.get("llm_calls", 0))
    for row in evaluation_rows:
        if row.get("evaluator_id") == "budget_compliance" and row.get("score") is not None:
            return float(row["score"])
    return 1.0


def record_positive_experience_sample(
    store: ResearchStore,
    *,
    run_id: UUID,
    owner_principal_id: UUID | None,
    strategy_key: str,
    quality: float,
    cost: float,
) -> None:
    store.record_learning_experience_sample(
        owner_principal_id=owner_principal_id,
        strategy_key=strategy_key,
        quality=quality,
        cost=cost,
        research_run_id=run_id,
    )


def observe_positive_experience_from_run(
    store: ResearchStore,
    run_id: UUID,
) -> LearningCase | None:
    """When a run passes evaluators, record sample and maybe emit optimization case."""
    row = store.get_run_row(run_id)
    if row is None or row.public_slug:
        return None
    evaluation_rows = store.list_evaluation_results(run_id)
    if not evaluation_rows:
        return None
    failed = [r for r in evaluation_rows if str(r.get("status")) in {"failed", "error"}]
    if failed:
        return None
    quality = _quality_score(evaluation_rows)
    if quality < QUALITY_PASS_THRESHOLD:
        return None
    consumption = store.get_consumption(run_id)
    cost = _cost_proxy(evaluation_rows, consumption)
    strategy_key = "default"
    snapshot = row.config_snapshot or {}
    policies = snapshot.get("learning_policies") or {}
    effective = policies.get("effective") or {}
    if effective.get("cost_latency", {}).get("prefer_lower_cost_strategy"):
        strategy_key = "lower_cost"
    record_positive_experience_sample(
        store,
        run_id=run_id,
        owner_principal_id=row.owner_principal_id,
        strategy_key=strategy_key,
        quality=quality,
        cost=cost,
    )
    baseline = store.aggregate_learning_experience(
        owner_principal_id=row.owner_principal_id,
        strategy_key="default",
    )
    candidate = store.aggregate_learning_experience(
        owner_principal_id=row.owner_principal_id,
        strategy_key=strategy_key,
    )
    if strategy_key == "default" or not baseline or not candidate:
        return None
    return observe_opportunity_from_metrics(
        case_id=f"positive-{run_id}",
        strategy_a={"quality": baseline["avg_quality"], "cost": baseline["avg_cost"]},
        strategy_b={"quality": candidate["avg_quality"], "cost": candidate["avg_cost"]},
        min_samples=MIN_POSITIVE_SAMPLES,
        sample_count=int(candidate.get("sample_count", 0)),
    )


def persist_positive_opportunity(store: ResearchStore, case: LearningCase) -> UUID | None:
    from deepscout_evaluation.learning.experience_store import persist_learning_case

    case.trust_level = TrustLevel.SANITIZED_CANDIDATE
    case.review_state = LearningCaseReviewState.OBSERVED
    case.failure_class = FailureClass.OPPORTUNITY.value
    case.subsystem = LearningSubsystem.COST
    case.origin = RegressionOrigin.PRODUCTION_CANDIDATE
    return persist_learning_case(store, case)
