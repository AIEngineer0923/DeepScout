"""Observe terminal runs and create sanitized learning cases."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_evaluation.learning.diagnosis import build_evaluator_signals, diagnose_learning_case
from deepscout_evaluation.learning.failure_taxonomy import FailureClass, from_evaluator_failure
from deepscout_evaluation.learning.models import (
    LearningCase,
    LearningCaseReviewState,
    LearningSubsystem,
    TrustLevel,
)
from deepscout_evaluation.learning.trust import sanitize_observation_payload
from deepscout_evaluation.regression_origins import RegressionOrigin


def _subsystem_for_failure(failure: FailureClass) -> LearningSubsystem:
    mapping = {
        FailureClass.PLANNING_FAILURE: LearningSubsystem.PLANNING,
        FailureClass.RETRIEVAL_FAILURE: LearningSubsystem.RETRIEVAL,
        FailureClass.EVIDENCE_FAILURE: LearningSubsystem.EVIDENCE,
        FailureClass.CLAIM_FAILURE: LearningSubsystem.CLAIMS,
        FailureClass.COVERAGE_FAILURE: LearningSubsystem.COVERAGE,
        FailureClass.SYNTHESIS_FAILURE: LearningSubsystem.SYNTHESIS,
        FailureClass.CITATION_FAILURE: LearningSubsystem.CITATION,
        FailureClass.COST_FAILURE: LearningSubsystem.COST,
        FailureClass.RUNTIME_FAILURE: LearningSubsystem.RUNTIME,
        FailureClass.SECURITY_FAILURE: LearningSubsystem.SECURITY,
        FailureClass.HITL_FAILURE: LearningSubsystem.HITL,
        FailureClass.OPPORTUNITY: LearningSubsystem.EVALUATION,
    }
    return mapping.get(failure, LearningSubsystem.EVALUATION)


def detect_failure_from_evaluations(
    evaluation_rows: list[dict[str, Any]],
    *,
    config_snapshot: dict[str, Any] | None = None,
) -> tuple[FailureClass | None, dict[str, Any]]:
    """Return earliest failure class and diagnostic evidence if any evaluator failed."""
    failed = [
        row for row in evaluation_rows if str(row.get("status")) in {"failed", "error"}
    ]
    if not failed:
        return None, {}

    failure = from_evaluator_failure(str(failed[0]["evaluator_id"]))
    evidence: dict[str, Any] = {
        "failed_evaluators": [
            {"evaluator_id": row["evaluator_id"], "reason": row.get("reason")}
            for row in failed
        ],
    }
    snapshot = config_snapshot or {}
    if snapshot.get("final_critic"):
        evidence["final_critic_verdict"] = snapshot["final_critic"].get("verdict")
    if snapshot.get("coverage_map"):
        gaps = [
            entry.get("requirement_id")
            for entry in snapshot["coverage_map"].get("entries", [])
            if entry.get("status") in {"SEARCHED_NO_EVIDENCE", "UNSUPPORTED", "PARTIAL"}
        ]
        if gaps:
            evidence["coverage_gap_ids"] = gaps
    return failure, evidence


def observe_from_evaluations(
    *,
    case_id: str,
    evaluation_rows: list[dict[str, Any]],
    config_snapshot: dict[str, Any] | None = None,
    research_run_id: UUID | None = None,
    owner_principal_id: UUID | None = None,
    origin: RegressionOrigin = RegressionOrigin.PRODUCTION_CANDIDATE,
    is_public_demo: bool = False,
) -> LearningCase | None:
    """Create a learning case from terminal evaluation rows. Returns None if no signal."""
    if is_public_demo:
        return None

    failure, evidence = detect_failure_from_evaluations(
        evaluation_rows, config_snapshot=config_snapshot
    )
    if failure is None:
        return None

    payload = {
        "symptom": f"evaluator failure: {evidence.get('failed_evaluators', [])}",
        "observed_behavior": str(evidence),
        "expected_behavior": "all applicable evaluators pass",
        "origin": origin.value,
    }
    sanitized, errors = sanitize_observation_payload(payload)
    if errors:
        return None

    case = LearningCase(
        case_id=case_id,
        subsystem=_subsystem_for_failure(failure),
        failure_class=failure.value,
        symptom=sanitized.get("symptom", ""),
        expected_behavior=sanitized.get("expected_behavior", ""),
        observed_behavior=sanitized.get("observed_behavior", ""),
        origin=origin,
        trust_level=TrustLevel.SANITIZED_CANDIDATE,
        review_state=LearningCaseReviewState.OBSERVED,
        sanitized=True,
        research_run_id=research_run_id,
        owner_principal_id=owner_principal_id,
        diagnostic_evidence=evidence,
        evaluator_signals=build_evaluator_signals(evaluation_rows),
        severity="high" if failure == FailureClass.SECURITY_FAILURE else "medium",
        confidence=0.7,
        reproducibility="production_observation",
    )
    return diagnose_learning_case(case)


def observe_opportunity_from_metrics(
    *,
    case_id: str,
    strategy_a: dict[str, float],
    strategy_b: dict[str, float],
    min_samples: int = 5,
    sample_count: int,
) -> LearningCase | None:
    """Detect optimization opportunity when B matches quality with lower cost/latency."""
    if sample_count < min_samples:
        return None
    quality_a = strategy_a.get("quality", 0.0)
    quality_b = strategy_b.get("quality", 0.0)
    cost_a = strategy_a.get("cost", 0.0)
    cost_b = strategy_b.get("cost", 0.0)
    if quality_b + 0.02 < quality_a:
        return None
    if cost_b >= cost_a * 0.9:
        return None
    return LearningCase(
        case_id=case_id,
        subsystem=LearningSubsystem.COST,
        failure_class=FailureClass.OPPORTUNITY.value,
        symptom="strategy B matches quality with lower cost",
        expected_behavior="prefer lower-cost strategy when quality equivalent",
        observed_behavior=f"A={strategy_a} B={strategy_b} samples={sample_count}",
        origin=RegressionOrigin.DEVELOPMENT_SYNTHETIC,
        trust_level=TrustLevel.VALIDATED_LEARNING,
        review_state=LearningCaseReviewState.DIAGNOSED,
        sanitized=True,
        diagnostic_evidence={"strategy_a": strategy_a, "strategy_b": strategy_b},
        confidence=min(0.9, 0.5 + sample_count * 0.05),
        reproducibility="aggregated_metrics",
    )
