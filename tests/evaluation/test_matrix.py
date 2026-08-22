from deepscout_evaluation.matrix import build_evaluation_rows
from deepscout_evaluation.registry import BUILTIN_EVALUATOR_MATRIX
from deepscout_evaluation.result_status import EvaluationResultStatus


def test_offline_evaluators_are_unavailable_not_blank() -> None:
    rows = build_evaluation_rows({})
    offline = next(row for row in rows if row["evaluator_id"] == "hallucination")
    assert offline["status"] == EvaluationResultStatus.UNAVAILABLE.value
    assert offline["reason"]


def test_not_applicable_conversation_evaluator_has_reason() -> None:
    rows = build_evaluation_rows({})
    row = next(item for item in rows if item["evaluator_id"] == "tone")
    assert row["status"] == EvaluationResultStatus.NOT_APPLICABLE.value
    assert row["reason"]


def test_active_evaluator_maps_budget_compliance() -> None:
    rows = build_evaluation_rows({"budget_compliance": True})
    row = next(item for item in rows if item["evaluator_id"] == "budget_compliance")
    assert row["status"] == EvaluationResultStatus.PASSED.value
    assert row["value"] is True


def test_matrix_covers_registry() -> None:
    rows = build_evaluation_rows({})
    assert len(rows) == len(BUILTIN_EVALUATOR_MATRIX)
