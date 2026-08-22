"""Map raw evaluator metrics to registry rows with explicit statuses."""

from __future__ import annotations

from deepscout_evaluation.registry import (
    BUILTIN_EVALUATOR_MATRIX,
    EvaluatorApplicability,
    EvaluatorSpec,
)
from deepscout_evaluation.result_status import EvaluationResultStatus


def _status_for_value(value: object | None) -> EvaluationResultStatus:
    if value is None:
        return EvaluationResultStatus.SKIPPED
    if isinstance(value, bool):
        return EvaluationResultStatus.PASSED if value else EvaluationResultStatus.FAILED
    if isinstance(value, (int, float)):
        return EvaluationResultStatus.SCORE
    return EvaluationResultStatus.SCORE


def _resolve_raw_value(spec: EvaluatorSpec, evals: dict[str, object]) -> object | None:
    value = evals.get(spec.evaluator_id)
    if value is not None:
        return value
    aliases = {
        "citation_correctness": "citation_resolve_rate",
        "provenance_complete": "provenance_complete_rate",
        "termination_correctness": "termination_correct",
        "budget_compliance": "budget_compliance",
        "plan_adherence": "plan_adherence",
        "tool_selection": "tool_selection",
        "trajectory_accuracy": "trajectory_accuracy",
    }
    alias = aliases.get(spec.evaluator_id)
    if alias:
        return evals.get(alias)
    return None


def _default_reason(
    spec: EvaluatorSpec,
    *,
    status: EvaluationResultStatus,
    value: object | None,
) -> str | None:
    if spec.applicability == EvaluatorApplicability.NOT_APPLICABLE_BY_DESIGN:
        return spec.description
    if spec.applicability == EvaluatorApplicability.FUTURE_MODALITY_GATED:
        return "This research product does not support this modality yet."
    if spec.applicability == EvaluatorApplicability.OFFLINE_ONLY:
        if spec.evaluator_id in {
            "retrieval_recall_at_k",
            "retrieval_precision_at_k",
            "retrieval_mrr",
            "ragas_context_precision",
            "ragas_faithfulness",
            "exact_match",
        }:
            return "Requires labeled ground truth or an offline evaluation dataset."
        return "Runs only in offline or advanced evaluation workflows."
    if spec.applicability == EvaluatorApplicability.UNSUPPORTED_BY_CURRENT_API:
        return "Not supported by the current API surface."
    if status == EvaluationResultStatus.SKIPPED:
        if spec.evaluator_id in {"citation_correctness", "provenance_complete"}:
            return "No evidence artifacts are available to verify this metric."
        if spec.evaluator_id == "claim_has_evidence":
            return "No evidence was captured for this research run."
        return "Required inputs were not available for this run."
    if status == EvaluationResultStatus.UNAVAILABLE:
        return "Evaluator is registered but not executable in the current environment."
    return None


def build_evaluation_rows(evals: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in BUILTIN_EVALUATOR_MATRIX:
        reason: str | None = None
        value: object | None = None
        status: EvaluationResultStatus

        if spec.applicability == EvaluatorApplicability.NOT_APPLICABLE_BY_DESIGN:
            status = EvaluationResultStatus.NOT_APPLICABLE
            reason = spec.description
        elif spec.applicability == EvaluatorApplicability.FUTURE_MODALITY_GATED:
            status = EvaluationResultStatus.NOT_APPLICABLE
            reason = "This research product does not support this modality yet."
        elif spec.applicability == EvaluatorApplicability.OFFLINE_ONLY:
            status = EvaluationResultStatus.UNAVAILABLE
            reason = _default_reason(spec, status=status, value=None)
        elif spec.applicability == EvaluatorApplicability.UNSUPPORTED_BY_CURRENT_API:
            status = EvaluationResultStatus.UNAVAILABLE
            reason = _default_reason(spec, status=status, value=None)
        else:
            value = _resolve_raw_value(spec, evals)
            explicit_status = evals.get(f"{spec.evaluator_id}__status")
            explicit_reason = evals.get(f"{spec.evaluator_id}__reason")
            if isinstance(explicit_status, str):
                status = EvaluationResultStatus(explicit_status)
            else:
                status = _status_for_value(value)
            reason = explicit_reason if isinstance(explicit_reason, str) else _default_reason(
                spec, status=status, value=value
            )

        rows.append(
            {
                "evaluator_id": spec.evaluator_id,
                "version": spec.version,
                "category": spec.category,
                "method": spec.method.value,
                "applicability": spec.applicability.value,
                "description": spec.description,
                "status": status.value,
                "value": value,
                "reason": reason,
            }
        )
    return rows
