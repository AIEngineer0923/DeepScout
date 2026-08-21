"""DeepScout evaluation registry — honest applicability, not fake coverage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvaluatorMethod(StrEnum):
    DETERMINISTIC_CODE = "deterministic_code"
    LLM_AS_JUDGE = "llm_as_judge"
    HYBRID = "hybrid"
    TRAJECTORY_MATCH = "trajectory_match"
    TRAJECTORY_LLM_JUDGE = "trajectory_llm_judge"
    HUMAN_FEEDBACK = "human_feedback"
    NOT_APPLICABLE = "not_applicable"


class EvaluatorApplicability(StrEnum):
    ACTIVE_NOW = "active_now"
    OFFLINE_ONLY = "offline_only"
    ONLINE_READY = "online_ready"
    FUTURE_MODALITY_GATED = "future_modality_gated"
    NOT_APPLICABLE_BY_DESIGN = "not_applicable_by_design"
    UNSUPPORTED_BY_CURRENT_API = "unsupported_by_current_api"


@dataclass(frozen=True, slots=True)
class EvaluatorSpec:
    evaluator_id: str
    version: str
    category: str
    method: EvaluatorMethod
    applicability: EvaluatorApplicability
    description: str


def _spec(
    evaluator_id: str,
    category: str,
    method: EvaluatorMethod,
    applicability: EvaluatorApplicability,
    description: str,
    *,
    version: str = "1",
) -> EvaluatorSpec:
    return EvaluatorSpec(evaluator_id, version, category, method, applicability, description)


BUILTIN_EVALUATOR_MATRIX: tuple[EvaluatorSpec, ...] = (
    # LangSmith generic catalog
    _spec("pii_leakage", "security", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "PII leakage"),
    _spec("prompt_injection", "security", EvaluatorMethod.HYBRID, EvaluatorApplicability.ACTIVE_NOW, "Prompt injection"),
    _spec("code_injection", "security", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Code injection"),
    _spec("toxicity", "safety", EvaluatorMethod.LLM_AS_JUDGE, EvaluatorApplicability.OFFLINE_ONLY, "Toxicity"),
    _spec("bias_fairness", "safety", EvaluatorMethod.LLM_AS_JUDGE, EvaluatorApplicability.OFFLINE_ONLY, "Bias & Fairness"),
    _spec("hallucination", "quality", EvaluatorMethod.LLM_AS_JUDGE, EvaluatorApplicability.OFFLINE_ONLY, "Hallucination"),
    _spec("correctness", "quality", EvaluatorMethod.HYBRID, EvaluatorApplicability.OFFLINE_ONLY, "Correctness"),
    _spec("assertions", "quality", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Assertions"),
    _spec("conciseness", "quality", EvaluatorMethod.LLM_AS_JUDGE, EvaluatorApplicability.OFFLINE_ONLY, "Conciseness"),
    _spec("code_checker", "quality", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.NOT_APPLICABLE_BY_DESIGN, "Code checker — DeepScout is not a coding agent"),
    _spec("answer_relevance", "quality", EvaluatorMethod.LLM_AS_JUDGE, EvaluatorApplicability.OFFLINE_ONLY, "Answer relevance"),
    _spec("exact_match", "quality", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.OFFLINE_ONLY, "Exact match"),
    _spec("perceived_error", "conversation", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.NOT_APPLICABLE_BY_DESIGN, "Perceived error — no chat product"),
    _spec("language", "conversation", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.NOT_APPLICABLE_BY_DESIGN, "Language — no chat product"),
    _spec("support_intent", "conversation", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.NOT_APPLICABLE_BY_DESIGN, "Support intent — no chat product"),
    _spec("user_satisfaction", "conversation", EvaluatorMethod.HUMAN_FEEDBACK, EvaluatorApplicability.NOT_APPLICABLE_BY_DESIGN, "User satisfaction — no chat product"),
    _spec("tone", "conversation", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.NOT_APPLICABLE_BY_DESIGN, "Tone — no chat product"),
    _spec("task_completion", "conversation", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Task completion via terminal run status"),
    _spec("knowledge_retention", "conversation", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.NOT_APPLICABLE_BY_DESIGN, "Knowledge retention — no multi-turn chat"),
    _spec("plan_adherence", "trajectory", EvaluatorMethod.TRAJECTORY_MATCH, EvaluatorApplicability.ACTIVE_NOW, "Plan adherence"),
    _spec("tool_selection", "trajectory", EvaluatorMethod.TRAJECTORY_MATCH, EvaluatorApplicability.ACTIVE_NOW, "Tool selection"),
    _spec("trajectory_accuracy", "trajectory", EvaluatorMethod.TRAJECTORY_MATCH, EvaluatorApplicability.ACTIVE_NOW, "Trajectory accuracy"),
    _spec("explicit_content", "image", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.FUTURE_MODALITY_GATED, "Explicit content"),
    _spec("sensitive_imagery", "image", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.FUTURE_MODALITY_GATED, "Sensitive imagery"),
    _spec("audio_quality", "voice", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.FUTURE_MODALITY_GATED, "Audio quality"),
    _spec("transcription_accuracy", "voice", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.FUTURE_MODALITY_GATED, "Transcription accuracy"),
    _spec("user_interrupts", "voice", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.FUTURE_MODALITY_GATED, "User interrupts"),
    _spec("vocal_affect", "voice", EvaluatorMethod.NOT_APPLICABLE, EvaluatorApplicability.FUTURE_MODALITY_GATED, "Vocal affect"),
    _spec("llm_judge", "create", EvaluatorMethod.LLM_AS_JUDGE, EvaluatorApplicability.OFFLINE_ONLY, "Generic LLM-as-a-Judge"),
    _spec("code_evaluator", "create", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ONLINE_READY, "LangSmith code evaluator"),
    # DeepScout-specific
    _spec("claim_has_evidence", "grounding", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Claim has evidence"),
    _spec("citation_correctness", "grounding", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Citation locator resolves"),
    _spec("provenance_complete", "grounding", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Claim/evidence/snapshot same run"),
    _spec("unsupported_claim_rate", "grounding", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Unsupported claim rate"),
    _spec("duplicate_work", "efficiency", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Duplicate work"),
    _spec("budget_compliance", "efficiency", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Budget compliance"),
    _spec("forbidden_tool", "agent_safety", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Forbidden tool usage"),
    _spec("dag_cycle_free", "plan", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "DAG cycle correctness"),
    _spec("termination_correctness", "trajectory", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Termination correctness"),
    _spec("secret_leakage", "security", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Secret leakage in traces"),
    _spec("ssrf_url", "security", EvaluatorMethod.DETERMINISTIC_CODE, EvaluatorApplicability.ACTIVE_NOW, "Malicious/private URL"),
)


def deterministic_claim_has_evidence(*, evidence_count: int) -> bool:
    from deepscout_evaluation.deterministic import eval_claim_has_evidence

    return eval_claim_has_evidence(evidence_count=evidence_count)
