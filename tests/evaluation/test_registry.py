"""Evaluation registry tests."""

from deepscout_evaluation.registry import (
    BUILTIN_EVALUATOR_MATRIX,
    deterministic_claim_has_evidence,
)


def test_builtin_evaluator_matrix_covers_security_and_grounding() -> None:
    ids = {spec.evaluator_id for spec in BUILTIN_EVALUATOR_MATRIX}
    assert "prompt_injection" in ids
    assert "claim_has_evidence" in ids
    assert "explicit_content" in ids
    assert "user_satisfaction" in ids
    assert "vocal_affect" in ids
    gated = {
        spec.evaluator_id
        for spec in BUILTIN_EVALUATOR_MATRIX
        if spec.applicability.value == "future_modality_gated"
    }
    assert "explicit_content" in gated
    assert "audio_quality" in gated


def test_deterministic_claim_has_evidence() -> None:
    assert deterministic_claim_has_evidence(evidence_count=1) is True
    assert deterministic_claim_has_evidence(evidence_count=0) is False
