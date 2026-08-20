"""DeepScout evaluation registry and deterministic evaluators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvaluatorMethod(StrEnum):
    DETERMINISTIC = "deterministic"
    ASSERTION = "assertion"
    LLM_JUDGE = "llm_judge"
    HYBRID = "hybrid"
    TRAJECTORY = "trajectory"
    NOT_APPLICABLE = "not_applicable"


class EvaluatorApplicability(StrEnum):
    ACTIVE_NOW = "active_now"
    OFFLINE_ONLY = "offline_only"
    ONLINE_READY = "online_ready"
    FUTURE_MODALITY_GATED = "future_modality_gated"
    NOT_APPLICABLE_BY_DESIGN = "not_applicable_by_design"


@dataclass(frozen=True, slots=True)
class EvaluatorSpec:
    evaluator_id: str
    version: str
    category: str
    method: EvaluatorMethod
    applicability: EvaluatorApplicability
    description: str


BUILTIN_EVALUATOR_MATRIX: tuple[EvaluatorSpec, ...] = (
    EvaluatorSpec("llm_judge", "1", "create", EvaluatorMethod.LLM_JUDGE, EvaluatorApplicability.OFFLINE_ONLY, "LLM-as-a-Judge"),
    EvaluatorSpec("code_evaluator", "1", "create", EvaluatorMethod.DETERMINISTIC, EvaluatorApplicability.ACTIVE_NOW, "Code Evaluator"),
    EvaluatorSpec("pii_leakage", "1", "security", EvaluatorMethod.DETERMINISTIC, EvaluatorApplicability.ACTIVE_NOW, "PII Leakage"),
    EvaluatorSpec("prompt_injection", "1", "security", EvaluatorMethod.HYBRID, EvaluatorApplicability.ACTIVE_NOW, "Prompt Injection"),
    EvaluatorSpec("hallucination", "1", "quality", EvaluatorMethod.LLM_JUDGE, EvaluatorApplicability.OFFLINE_ONLY, "Hallucination"),
    EvaluatorSpec("plan_adherence", "1", "trajectory", EvaluatorMethod.TRAJECTORY, EvaluatorApplicability.OFFLINE_ONLY, "Plan Adherence"),
    EvaluatorSpec("explicit_content", "1", "image", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.FUTURE_MODALITY_GATED, "Explicit Content"),
    EvaluatorSpec("audio_quality", "1", "voice", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.FUTURE_MODALITY_GATED, "Audio Quality"),
    EvaluatorSpec("claim_has_evidence", "1", "grounding", EvaluatorMethod.DETERMINISTIC, EvaluatorApplicability.ACTIVE_NOW, "Claim has evidence"),
    EvaluatorSpec("citation_correctness", "1", "grounding", EvaluatorMethod.DETERMINISTIC, EvaluatorApplicability.ACTIVE_NOW, "Citation correctness"),
    EvaluatorSpec("duplicate_work", "1", "efficiency", EvaluatorMethod.DETERMINISTIC, EvaluatorApplicability.ACTIVE_NOW, "Duplicate work"),
)


def deterministic_claim_has_evidence(*, evidence_count: int) -> bool:
    return evidence_count > 0
