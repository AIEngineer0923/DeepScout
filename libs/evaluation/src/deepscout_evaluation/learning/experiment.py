"""Deterministic baseline vs candidate experimentation — no provider calls."""

from __future__ import annotations

from typing import Any

from deepscout_evaluation.learning.models import (
    ExperimentComparison,
    ExperimentDimension,
    ExperimentOutcome,
    ImprovementCandidate,
)


def _score_fixture(policy: dict[str, Any], fixture: dict[str, Any]) -> dict[str, float]:
    """Deterministic scorer for learning-loop fixtures (not live retrieval quality)."""
    base_quality = float(fixture.get("baseline_quality", 0.7))
    base_cost = float(fixture.get("baseline_cost", 1.0))
    base_latency = float(fixture.get("baseline_latency_ms", 1000))
    coverage = float(fixture.get("coverage_score", 0.8))
    security = float(fixture.get("security_score", 1.0))

    bonus = int(policy.get("gap_queries_per_round_bonus", 0))
    cost_mult = float(policy.get("retrieval_candidate_k_multiplier", 1.0))
    prefer_low_cost = bool(policy.get("prefer_lower_cost_strategy", False))

    quality = base_quality
    cost = base_cost
    latency = base_latency

    if fixture.get("failure_class") == "coverage_failure":
        quality += 0.08 * bonus
        cost += 0.05 * bonus
        latency += 50 * bonus
    if fixture.get("failure_class") == "retrieval_failure":
        quality += 0.05 * (cost_mult - 1.0) * 10
        cost += 0.1 * (cost_mult - 1.0) * 10
        latency += 80 * (cost_mult - 1.0) * 10
    if fixture.get("failure_class") == "planning_failure":
        strict = float(policy.get("planner_decomposition_strictness", 0.5))
        quality += 0.06 * (strict - 0.5)
        cost += 0.04 * max(0, strict - 0.5)
    if fixture.get("failure_class") == "runtime_failure":
        parallel = float(policy.get("allocation_parallel_preference", 0.5))
        cost += 0.08 * parallel
        latency -= 40 * parallel
    if fixture.get("failure_class") == "synthesis_failure":
        rewrite = int(policy.get("report_rewrite_bonus", 0))
        quality += 0.07 * rewrite
        cost += 0.06 * rewrite
    if prefer_low_cost and fixture.get("scenario") == "opportunity":
        cost *= 0.85
    if fixture.get("scenario") == "security_regression":
        if policy.get("gap_queries_per_round_bonus", 0) > 0:
            security -= 0.2

    return {
        "quality": min(1.0, quality),
        "coverage": min(1.0, coverage + 0.05 * bonus),
        "cost": cost,
        "latency_ms": latency,
        "security": max(0.0, security),
    }


def run_experiment(
    *,
    case_id: str,
    baseline_policy: dict[str, Any],
    candidate: ImprovementCandidate,
    fixture: dict[str, Any],
) -> ExperimentComparison:
    candidate_policy = {**baseline_policy, **candidate.policy_delta}
    baseline_scores = _score_fixture(baseline_policy, fixture)
    candidate_scores = _score_fixture(candidate_policy, fixture)

    dimensions: list[ExperimentDimension] = []
    for name in ("quality", "coverage", "security"):
        base_val = baseline_scores[name]
        cand_val = candidate_scores[name]
        delta = cand_val - base_val
        if name == "security":
            improved = True if delta > 0.001 else (False if delta < -0.001 else None)
        else:
            improved = True if delta > 0.01 else (False if delta < -0.01 else None)
        dimensions.append(
            ExperimentDimension(
                name=name,
                baseline=base_val,
                candidate=cand_val,
                delta=delta,
                weight=2.0 if name == "quality" else 1.0,
                improved=improved,
            )
        )
    for name, weight in (("cost", 1.0), ("latency_ms", 0.5)):
        base_val = baseline_scores[name]
        cand_val = candidate_scores[name]
        delta = cand_val - base_val
        improved = True if delta < -0.01 else (False if delta > 0.01 else None)
        dimensions.append(
            ExperimentDimension(
                name=name,
                baseline=base_val,
                candidate=cand_val,
                delta=delta,
                weight=weight,
                improved=improved,
            )
        )

    quality_delta = candidate_scores["quality"] - baseline_scores["quality"]
    cost_delta = candidate_scores["cost"] - baseline_scores["cost"]
    latency_delta = candidate_scores["latency_ms"] - baseline_scores["latency_ms"]
    security_regressed = candidate_scores["security"] < baseline_scores["security"] - 0.001

    improved_dims = sum(1 for dim in dimensions if dim.improved is True)
    regressed_dims = sum(1 for dim in dimensions if dim.improved is False)

    if security_regressed:
        outcome = ExperimentOutcome.REGRESSED
    elif (
        fixture.get("failure_class") == "retrieval_failure"
        and quality_delta >= 0.04
        and not security_regressed
    ):
        outcome = ExperimentOutcome.IMPROVED
    elif regressed_dims > improved_dims:
        outcome = ExperimentOutcome.REGRESSED
    elif improved_dims == 0 and regressed_dims == 0:
        outcome = ExperimentOutcome.NEUTRAL
    elif quality_delta >= 0.02 and improved_dims >= regressed_dims:
        outcome = ExperimentOutcome.IMPROVED
    elif improved_dims > 0 and regressed_dims == 0:
        outcome = ExperimentOutcome.IMPROVED
    else:
        outcome = ExperimentOutcome.INCONCLUSIVE

    return ExperimentComparison(
        case_id=case_id,
        baseline_policy=baseline_policy,
        candidate_policy=candidate_policy,
        dimensions=dimensions,
        outcome=outcome,
        quality_delta=quality_delta,
        cost_delta=cost_delta,
        latency_delta=latency_delta,
        security_regressed=security_regressed,
    )
