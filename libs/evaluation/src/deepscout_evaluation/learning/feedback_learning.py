"""User feedback → low-trust learning signals."""

from __future__ import annotations

from uuid import UUID

from deepscout_evaluation.learning.failure_taxonomy import FailureClass
from deepscout_evaluation.learning.models import (
    LearningCase,
    LearningCaseReviewState,
    LearningSubsystem,
    TrustLevel,
)
from deepscout_evaluation.learning.trust import sanitize_observation_payload
from deepscout_evaluation.regression_origins import RegressionOrigin

_FEEDBACK_TARGET_SUBSYSTEM = {
    "report": LearningSubsystem.SYNTHESIS,
    "claim": LearningSubsystem.CLAIMS,
    "evidence": LearningSubsystem.EVIDENCE,
    "retrieval": LearningSubsystem.RETRIEVAL,
    "overall": LearningSubsystem.EVALUATION,
}

_FEEDBACK_FAILURE = {
    "useful": None,
    "incorrect": FailureClass.CLAIM_FAILURE,
    "missing_information": FailureClass.COVERAGE_FAILURE,
    "bad_source": FailureClass.RETRIEVAL_FAILURE,
    "citation_issue": FailureClass.CITATION_FAILURE,
}


def learning_case_from_human_feedback(
    *,
    feedback_id: UUID,
    research_run_id: UUID,
    owner_principal_id: UUID | None,
    target_type: str,
    rating: str | None,
    comment: str | None,
    labels: list[str] | None,
) -> LearningCase | None:
    """User feedback is observational — never verified ground truth."""
    label = (labels or [None])[0] or rating or "feedback"
    failure = _FEEDBACK_FAILURE.get(str(label).lower())
    if failure is None and str(label).lower() == "useful":
        return None
    if failure is None:
        failure = FailureClass.SYNTHESIS_FAILURE
    payload = {
        "symptom": f"user feedback: {label}",
        "observed_behavior": (comment or "")[:2000],
        "expected_behavior": "user-expected research quality",
        "origin": RegressionOrigin.PRODUCTION_CANDIDATE.value,
    }
    sanitized, errors = sanitize_observation_payload(payload)
    if errors:
        return None
    return LearningCase(
        case_id=f"feedback-{feedback_id}",
        subsystem=_FEEDBACK_TARGET_SUBSYSTEM.get(target_type, LearningSubsystem.EVALUATION),
        failure_class=failure.value,
        symptom=sanitized.get("symptom", ""),
        expected_behavior=sanitized.get("expected_behavior", ""),
        observed_behavior=sanitized.get("observed_behavior", ""),
        origin=RegressionOrigin.PRODUCTION_CANDIDATE,
        trust_level=TrustLevel.UNTRUSTED_OBSERVATION,
        review_state=LearningCaseReviewState.OBSERVED,
        sanitized=True,
        research_run_id=research_run_id,
        owner_principal_id=owner_principal_id,
        diagnostic_evidence={"feedback_label": label, "target_type": target_type},
        severity="low",
        confidence=0.4,
        reproducibility="user_feedback",
    )
