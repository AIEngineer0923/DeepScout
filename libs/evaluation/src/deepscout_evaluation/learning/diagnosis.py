"""Root-cause diagnosis from evaluator signals and critic traces."""

from __future__ import annotations

from typing import Any

from deepscout_evaluation.learning.failure_taxonomy import (
    FailureClass,
    earliest_root_cause,
    from_evaluator_failure,
    from_final_critic_verdict,
    from_retrieval_failure,
    is_downstream_symptom,
)
from deepscout_evaluation.learning.models import LearningCase, LearningCaseReviewState


def diagnose_learning_case(case: LearningCase) -> LearningCase:
    """Attribute earliest defensible causal stage from diagnostic evidence."""
    candidates: list[FailureClass] = []
    signals = case.evaluator_signals
    for evaluator_id, status in signals.items():
        if status == "failed":
            candidates.append(from_evaluator_failure(str(evaluator_id)))

    retrieval_class = case.diagnostic_evidence.get("retrieval_failure_class")
    if retrieval_class:
        candidates.append(from_retrieval_failure(str(retrieval_class)))

    critic_verdict = case.diagnostic_evidence.get("final_critic_verdict")
    if critic_verdict:
        symptom = from_final_critic_verdict(str(critic_verdict))
        candidates.append(symptom)
        if case.failure_class and case.failure_class != symptom.value:
            case.is_root_cause = is_downstream_symptom(
                FailureClass(case.failure_class), symptom
            )

    coverage_gaps = case.diagnostic_evidence.get("coverage_gap_ids") or []
    if coverage_gaps and FailureClass.COVERAGE_FAILURE not in candidates:
        candidates.append(FailureClass.COVERAGE_FAILURE)

    root = earliest_root_cause(candidates) if candidates else FailureClass(case.failure_class)
    case.root_cause_class = root.value
    case.is_root_cause = case.failure_class == root.value
    case.review_state = LearningCaseReviewState.DIAGNOSED
    if not case.is_root_cause and case.root_cause_class:
        case.downstream_symptom_of = case.root_cause_class
    return case


def build_evaluator_signals(evaluation_rows: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(row["evaluator_id"]): str(row.get("status", "unknown"))
        for row in evaluation_rows
        if row.get("status") in {"failed", "passed", "score"}
    }
