"""Authoritative HITL review events → higher-trust learning signals."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_evaluation.learning.failure_taxonomy import FailureClass
from deepscout_evaluation.learning.models import (
    LearningCase,
    LearningCaseReviewState,
    LearningSubsystem,
    TrustLevel,
)
from deepscout_evaluation.regression_origins import RegressionOrigin

_HITL_EVENT_MAP: dict[str, tuple[LearningSubsystem, str]] = {
    "candidate_rejected": (LearningSubsystem.EVALUATION, "candidate rejected by reviewer"),
    "candidate_approved": (LearningSubsystem.EVALUATION, "candidate approved by reviewer"),
    "budget_continuation_rejected": (LearningSubsystem.RUNTIME, "budget continuation rejected"),
    "scope_edited": (LearningSubsystem.PLANNING, "operator edited research scope"),
    "operator_correction": (LearningSubsystem.SYNTHESIS, "operator correction recorded"),
}


def learning_case_from_hitl_event(
    *,
    event_type: str,
    research_run_id: UUID | None,
    owner_principal_id: UUID | None,
    payload: dict[str, Any] | None,
    event_id: UUID,
) -> LearningCase | None:
    mapped = _HITL_EVENT_MAP.get(event_type)
    if mapped is None:
        return None
    subsystem, symptom = mapped
    return LearningCase(
        case_id=f"hitl-{event_id}",
        subsystem=subsystem,
        failure_class=FailureClass.HITL_FAILURE.value
        if "rejected" in event_type
        else FailureClass.OPPORTUNITY.value,
        symptom=symptom,
        expected_behavior="authoritative human review outcome",
        observed_behavior=str(payload or {})[:2000],
        origin=RegressionOrigin.PRODUCTION_CANDIDATE,
        trust_level=TrustLevel.REVIEWED_CASE,
        review_state=LearningCaseReviewState.OBSERVED,
        sanitized=True,
        research_run_id=research_run_id,
        owner_principal_id=owner_principal_id,
        diagnostic_evidence={"hitl_event_type": event_type, **(payload or {})},
        severity="medium",
        confidence=0.85,
        reproducibility="hitl_review_event",
    )
