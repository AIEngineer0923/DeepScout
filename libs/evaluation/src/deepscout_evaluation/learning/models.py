"""Typed learning-case and improvement-candidate models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from deepscout_evaluation.regression_origins import RegressionOrigin


class LearningSubsystem(StrEnum):
    PLANNING = "planning"
    RETRIEVAL = "retrieval"
    EVIDENCE = "evidence"
    CLAIMS = "claims"
    COVERAGE = "coverage"
    SYNTHESIS = "synthesis"
    CITATION = "citation"
    EVALUATION = "evaluation"
    COST = "cost"
    RUNTIME = "runtime"
    SECURITY = "security"
    HITL = "hitl"


class LearningCaseReviewState(StrEnum):
    OBSERVED = "observed"
    DIAGNOSED = "diagnosed"
    CANDIDATE_PENDING = "candidate_pending"
    REVIEWED = "reviewed"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class TrustLevel(StrEnum):
    UNTRUSTED_OBSERVATION = "untrusted_observation"
    SANITIZED_CANDIDATE = "sanitized_candidate"
    REVIEWED_CASE = "reviewed_case"
    VALIDATED_LEARNING = "validated_learning"
    PROMOTED_POLICY = "promoted_policy"


class ImprovementCandidateType(StrEnum):
    CONFIGURATION = "configuration"
    POLICY = "policy"
    PROMPT = "prompt"
    ROUTING = "routing"
    QUERY_STRATEGY = "query_strategy"
    RETRIEVAL_PARAMETER = "retrieval_parameter"
    RERANK_POLICY = "rerank_policy"
    PLANNER_POLICY = "planner_policy"
    WORKER_POLICY = "worker_policy"
    COVERAGE_POLICY = "coverage_policy"
    SYNTHESIS_POLICY = "synthesis_policy"
    STOPPING_POLICY = "stopping_policy"
    CODE_PROPOSAL = "code_proposal"


class ImprovementCandidateStatus(StrEnum):
    DRAFT = "draft"
    EVALUATED = "evaluated"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"


class ExperimentOutcome(StrEnum):
    IMPROVED = "improved"
    NEUTRAL = "neutral"
    REGRESSED = "regressed"
    INCONCLUSIVE = "inconclusive"


class PromotionVerdict(StrEnum):
    SAFE_TO_PROMOTE = "safe_to_promote"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"
    REJECTED = "rejected"
    NO_CHANGE = "no_change"


class LearningCase(BaseModel):
    case_id: str
    subsystem: LearningSubsystem
    failure_class: str
    symptom: str
    expected_behavior: str
    observed_behavior: str
    origin: RegressionOrigin = RegressionOrigin.DEVELOPMENT_SYNTHETIC
    trust_level: TrustLevel = TrustLevel.UNTRUSTED_OBSERVATION
    review_state: LearningCaseReviewState = LearningCaseReviewState.OBSERVED
    sanitized: bool = False
    human_reviewed: bool = False
    research_run_id: UUID | None = None
    owner_principal_id: UUID | None = None
    root_cause_class: str | None = None
    is_root_cause: bool = True
    downstream_symptom_of: str | None = None
    diagnostic_evidence: dict[str, Any] = Field(default_factory=dict)
    evaluator_signals: dict[str, Any] = Field(default_factory=dict)
    affected_requirements: list[str] = Field(default_factory=list)
    severity: str = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reproducibility: str = "deterministic_fixture"
    user_visible_impact: str = ""
    cost_impact: str = ""
    latency_impact: str = ""
    security_impact: str = ""
    architecture_version: str = "learning-v1"
    created_at: datetime | None = None

    def to_store_dict(self) -> dict[str, Any]:
        return {
            "case_key": self.case_id,
            "subsystem": self.subsystem.value,
            "failure_class": self.failure_class,
            "symptom": self.symptom,
            "expected_behavior": self.expected_behavior,
            "observed_behavior": self.observed_behavior,
            "origin": self.origin.value,
            "trust_level": self.trust_level.value,
            "review_state": self.review_state.value,
            "sanitized": self.sanitized,
            "human_reviewed": self.human_reviewed,
            "research_run_id": self.research_run_id,
            "owner_principal_id": self.owner_principal_id,
            "root_cause_class": self.root_cause_class,
            "is_root_cause": self.is_root_cause,
            "downstream_symptom_of": self.downstream_symptom_of,
            "diagnostic_evidence": self.diagnostic_evidence,
            "evaluator_signals": self.evaluator_signals,
            "affected_requirements": self.affected_requirements,
            "severity": self.severity,
            "confidence": self.confidence,
            "reproducibility": self.reproducibility,
            "user_visible_impact": self.user_visible_impact,
            "cost_impact": self.cost_impact,
            "latency_impact": self.latency_impact,
            "security_impact": self.security_impact,
            "architecture_version": self.architecture_version,
        }


class ImprovementCandidate(BaseModel):
    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
    learning_case_id: str
    candidate_type: ImprovementCandidateType
    title: str
    rationale: str
    policy_delta: dict[str, Any] = Field(default_factory=dict)
    expected_benefit: str = ""
    possible_regressions: str = ""
    affected_subsystem: LearningSubsystem
    evaluation_plan: dict[str, Any] = Field(default_factory=dict)
    supporting_case_ids: list[str] = Field(default_factory=list)
    trust_level: TrustLevel = TrustLevel.SANITIZED_CANDIDATE
    status: ImprovementCandidateStatus = ImprovementCandidateStatus.DRAFT
    owner_principal_id: UUID | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rollback_info: dict[str, Any] = Field(default_factory=dict)

    def to_store_dict(self) -> dict[str, Any]:
        return {
            "candidate_key": self.candidate_id,
            "learning_case_key": self.learning_case_id,
            "candidate_type": self.candidate_type.value,
            "title": self.title,
            "rationale": self.rationale,
            "policy_delta": self.policy_delta,
            "expected_benefit": self.expected_benefit,
            "possible_regressions": self.possible_regressions,
            "affected_subsystem": self.affected_subsystem.value,
            "evaluation_plan": self.evaluation_plan,
            "supporting_case_ids": self.supporting_case_ids,
            "trust_level": self.trust_level.value,
            "status": self.status.value,
            "owner_principal_id": self.owner_principal_id,
            "confidence": self.confidence,
            "rollback_info": self.rollback_info,
        }


class ExperimentDimension(BaseModel):
    name: str
    baseline: float
    candidate: float
    delta: float
    weight: float = 1.0
    improved: bool | None = None


class ExperimentComparison(BaseModel):
    case_id: str
    baseline_policy: dict[str, Any]
    candidate_policy: dict[str, Any]
    dimensions: list[ExperimentDimension]
    outcome: ExperimentOutcome
    quality_delta: float = 0.0
    cost_delta: float = 0.0
    latency_delta: float = 0.0
    security_regressed: bool = False
    notes: str = ""


class PromotionDecision(BaseModel):
    candidate_id: str
    verdict: PromotionVerdict
    outcome: ExperimentOutcome
    reasons: list[str] = Field(default_factory=list)
    requires_human: bool = False
    policy_version_label: str | None = None


class PolicyVersion(BaseModel):
    policy_key: str
    version_label: str
    payload: dict[str, Any] = Field(default_factory=dict)
    active: bool = False
    promoted_from_candidate_id: str | None = None
    promotion_reason: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    owner_principal_id: UUID | None = None
    policy_family: str | None = None
    scope_key: str | None = None
