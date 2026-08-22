"""Failure taxonomy — extends RetrievalFailureClass with system-wide stages."""

from __future__ import annotations

from enum import StrEnum

from deepscout_core.domain.contracts import RetrievalFailureClass


class FailureClass(StrEnum):
    """Earliest defensible causal stage for learning attribution."""

    PLANNING_FAILURE = "planning_failure"
    RETRIEVAL_FAILURE = "retrieval_failure"
    EVIDENCE_FAILURE = "evidence_failure"
    CLAIM_FAILURE = "claim_failure"
    COVERAGE_FAILURE = "coverage_failure"
    SYNTHESIS_FAILURE = "synthesis_failure"
    CITATION_FAILURE = "citation_failure"
    EVALUATION_FAILURE = "evaluation_failure"
    COST_FAILURE = "cost_failure"
    RUNTIME_FAILURE = "runtime_failure"
    SECURITY_FAILURE = "security_failure"
    HITL_FAILURE = "hitl_failure"
    OPPORTUNITY = "opportunity"


_RETRIEVAL_MAP: dict[RetrievalFailureClass, FailureClass] = {
    RetrievalFailureClass.ROUTING_FAILURE: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.LEXICAL_RETRIEVAL_FAILURE: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.DENSE_RETRIEVAL_FAILURE: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.FUSION_FAILURE: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.RERANK_FAILURE: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.GRAPH_RETRIEVAL_FAILURE: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.COMPILED_KNOWLEDGE_FAILURE: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.PROVENANCE_FAILURE: FailureClass.EVIDENCE_FAILURE,
    RetrievalFailureClass.SEARCH_DID_NOT_SURFACE_SOURCE: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.SOURCE_FETCH_FAILED: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.SOURCE_NOT_ADMISSIBLE: FailureClass.EVIDENCE_FAILURE,
    RetrievalFailureClass.ENTITY_EXTRACTION_FAILED: FailureClass.EVIDENCE_FAILURE,
    RetrievalFailureClass.ENTITY_NOT_CURRENT: FailureClass.EVIDENCE_FAILURE,
    RetrievalFailureClass.EVIDENCE_NOT_VERIFIED: FailureClass.EVIDENCE_FAILURE,
    RetrievalFailureClass.LEGAL_REFERENCE_UNRESOLVED: FailureClass.CLAIM_FAILURE,
    RetrievalFailureClass.NO_ANSWER_FALSE_POSITIVE: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.NO_ANSWER_FALSE_NEGATIVE: FailureClass.RETRIEVAL_FAILURE,
    RetrievalFailureClass.CONTENT_EXTRACTION_FAILURE: FailureClass.EVIDENCE_FAILURE,
}

_EVALUATOR_FAILURE_MAP: dict[str, FailureClass] = {
    "claim_has_evidence": FailureClass.CLAIM_FAILURE,
    "unsupported_claim_rate": FailureClass.CLAIM_FAILURE,
    "quote_resolves": FailureClass.CITATION_FAILURE,
    "provenance_complete": FailureClass.EVIDENCE_FAILURE,
    "budget_compliance": FailureClass.COST_FAILURE,
    "duplicate_work": FailureClass.RUNTIME_FAILURE,
    "dag_valid": FailureClass.PLANNING_FAILURE,
    "trajectory_match": FailureClass.PLANNING_FAILURE,
    "termination_correct": FailureClass.RUNTIME_FAILURE,
    "retrieval_cross_run_isolation": FailureClass.SECURITY_FAILURE,
    "secret_leakage": FailureClass.SECURITY_FAILURE,
    "pii_leakage": FailureClass.SECURITY_FAILURE,
    "prompt_injection": FailureClass.SECURITY_FAILURE,
    "ssrf_urls": FailureClass.SECURITY_FAILURE,
}

_CAUSAL_ORDER: tuple[FailureClass, ...] = (
    FailureClass.PLANNING_FAILURE,
    FailureClass.RETRIEVAL_FAILURE,
    FailureClass.EVIDENCE_FAILURE,
    FailureClass.CLAIM_FAILURE,
    FailureClass.COVERAGE_FAILURE,
    FailureClass.CITATION_FAILURE,
    FailureClass.SYNTHESIS_FAILURE,
    FailureClass.EVALUATION_FAILURE,
    FailureClass.COST_FAILURE,
    FailureClass.RUNTIME_FAILURE,
    FailureClass.SECURITY_FAILURE,
    FailureClass.HITL_FAILURE,
)


def from_retrieval_failure(value: str | RetrievalFailureClass) -> FailureClass:
    try:
        parsed = (
            value if isinstance(value, RetrievalFailureClass) else RetrievalFailureClass(value)
        )
    except ValueError:
        return FailureClass.RETRIEVAL_FAILURE
    return _RETRIEVAL_MAP.get(parsed, FailureClass.RETRIEVAL_FAILURE)


def from_evaluator_failure(evaluator_id: str) -> FailureClass:
    return _EVALUATOR_FAILURE_MAP.get(evaluator_id, FailureClass.EVALUATION_FAILURE)


def from_final_critic_verdict(verdict: str) -> FailureClass:
    normalized = verdict.strip().upper()
    if normalized == "BLOCKED_BY_EVIDENCE":
        return FailureClass.EVIDENCE_FAILURE
    if normalized == "RESEARCH_GAP":
        return FailureClass.COVERAGE_FAILURE
    if normalized == "REVISION_REQUIRED":
        return FailureClass.SYNTHESIS_FAILURE
    return FailureClass.EVALUATION_FAILURE


def is_downstream_symptom(symptom: FailureClass, root: FailureClass) -> bool:
    if symptom == root:
        return False
    try:
        return _CAUSAL_ORDER.index(symptom) > _CAUSAL_ORDER.index(root)
    except ValueError:
        return False


def earliest_root_cause(candidates: list[FailureClass]) -> FailureClass:
    if not candidates:
        return FailureClass.EVALUATION_FAILURE
    ordered = sorted(candidates, key=lambda item: _CAUSAL_ORDER.index(item))
    return ordered[0]
