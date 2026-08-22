"""Learning and self-improvement APIs — owner-scoped, no demo mutation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_core.settings import Settings, get_settings
from deepscout_evaluation.learning.candidates import generate_improvement_candidate
from deepscout_evaluation.learning.diagnosis import diagnose_learning_case
from deepscout_evaluation.learning.experience_store import (
    list_improvement_candidates_for_owner,
    list_learning_cases_for_owner,
)
from deepscout_evaluation.learning.experiment import run_experiment
from deepscout_evaluation.learning.models import (
    ImprovementCandidateStatus,
    LearningCase,
    LearningCaseReviewState,
    LearningSubsystem,
    PromotionVerdict,
    TrustLevel,
)
from deepscout_evaluation.learning.policy import apply_promotion
from deepscout_evaluation.learning.policy_families import (
    PolicyFamily,
    family_for_payload_delta,
    merge_baseline,
    policy_key_for,
)
from deepscout_evaluation.learning.promotion import evaluate_promotion
from deepscout_evaluation.regression_origins import RegressionOrigin
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deepscout_api.access import load_access, require_user
from deepscout_api.deps import get_research_store

router = APIRouter(tags=["learning"])


class LearningCaseRead(BaseModel):
    id: UUID
    case_key: str
    subsystem: str
    failure_class: str
    symptom: str
    review_state: str
    trust_level: str
    root_cause_class: str | None = None
    confidence: float | None = None
    created_at: Any


class ImprovementCandidateRead(BaseModel):
    id: UUID
    candidate_key: str
    title: str
    status: str
    candidate_type: str
    promotion_verdict: str | None = None
    policy_delta: dict[str, Any] | None = None
    created_at: Any


class PolicyVersionRead(BaseModel):
    id: UUID
    policy_key: str
    policy_family: str | None = None
    version_label: str
    active: bool
    promotion_reason: str | None = None
    created_at: Any


class AuditEventRead(BaseModel):
    id: UUID
    event_type: str
    policy_key: str | None = None
    policy_family: str | None = None
    previous_version_label: str | None = None
    new_version_label: str | None = None
    reason: str | None = None
    actor_label: str
    created_at: Any


class LearningMetricsRead(BaseModel):
    cases_total: int = 0
    cases_open: int = 0
    cases_diagnosed: int = 0
    candidates_proposed: int = 0
    candidates_evaluated: int = 0
    candidates_promoted: int = 0
    candidates_rejected: int = 0
    candidates_requires_review: int = 0
    active_policy_versions: int = 0


class ApproveCandidateBody(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class RollbackPolicyBody(BaseModel):
    policy_key: str
    reason: str = Field(default="operator rollback", max_length=2000)


def _require_learning(store) -> None:
    if not store.learning_tables_available():
        raise HTTPException(status_code=503, detail="Learning store unavailable")


@router.get("/api/v1/learning/cases", response_model=list[LearningCaseRead])
def list_learning_cases(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> list[LearningCaseRead]:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    rows = list_learning_cases_for_owner(store, principal.id)
    return [LearningCaseRead(**row) for row in rows]


@router.get("/api/v1/learning/candidates", response_model=list[ImprovementCandidateRead])
def list_candidates(
    request: Request,
    status: str | None = None,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> list[ImprovementCandidateRead]:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    rows = list_improvement_candidates_for_owner(store, principal.id, status=status)
    return [ImprovementCandidateRead(**row) for row in rows]


@router.get("/api/v1/learning/metrics", response_model=LearningMetricsRead)
def learning_metrics(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> LearningMetricsRead:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    _require_learning(store)
    return LearningMetricsRead(**store.get_learning_metrics(owner_principal_id=principal.id))


@router.get("/api/v1/learning/policies", response_model=list[PolicyVersionRead])
def list_policies(
    request: Request,
    policy_key: str | None = None,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> list[PolicyVersionRead]:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    _require_learning(store)
    rows = store.list_learning_policy_versions(
        policy_key=policy_key, owner_principal_id=principal.id
    )
    return [PolicyVersionRead(**row) for row in rows]


@router.get("/api/v1/learning/audit", response_model=list[AuditEventRead])
def list_audit(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> list[AuditEventRead]:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    rows = store.list_learning_audit_events(owner_principal_id=principal.id)
    return [AuditEventRead(**row) for row in rows]


@router.post("/api/v1/learning/candidates/{candidate_id}/approve")
def approve_candidate(
    candidate_id: UUID,
    body: ApproveCandidateBody,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    access = load_access(request, store._session, settings)
    require_user(access)
    _require_learning(store)
    updated = store.update_improvement_candidate_status(
        candidate_id,
        status=ImprovementCandidateStatus.APPROVED.value,
        promotion_verdict=PromotionVerdict.REQUIRES_HUMAN_REVIEW.value,
        promotion_reason=body.reason or "approved by operator",
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"status": ImprovementCandidateStatus.APPROVED.value}


@router.post("/api/v1/learning/candidates/{candidate_id}/reject")
def reject_candidate(
    candidate_id: UUID,
    body: ApproveCandidateBody,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    access = load_access(request, store._session, settings)
    require_user(access)
    _require_learning(store)
    updated = store.update_improvement_candidate_status(
        candidate_id,
        status=ImprovementCandidateStatus.REJECTED.value,
        promotion_verdict=PromotionVerdict.REJECTED.value,
        promotion_reason=body.reason or "rejected by operator",
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"status": ImprovementCandidateStatus.REJECTED.value}


@router.post("/api/v1/learning/policies/rollback")
def rollback_policy(
    body: RollbackPolicyBody,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    _require_learning(store)
    rolled = store.rollback_learning_policy(
        policy_key=body.policy_key,
        owner_principal_id=principal.id,
        rollback_reason=body.reason,
        actor=str(principal.id),
    )
    if rolled is None:
        raise HTTPException(status_code=404, detail="No policy to rollback")
    store._session.commit()
    return {"status": "rolled_back", "version_id": str(rolled)}


@router.post("/api/v1/learning/smoke/controlled")
def controlled_smoke_promote(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Operator-only controlled smoke — requires authenticated owner."""
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    _require_learning(store)
    case = diagnose_learning_case(
        LearningCase(
            case_id=f"api-smoke-{principal.id.hex[:8]}",
            subsystem=LearningSubsystem.RETRIEVAL,
            failure_class="retrieval_failure",
            symptom="controlled API smoke",
            expected_behavior="bounded retrieval adaptation",
            observed_behavior="deterministic smoke",
            origin=RegressionOrigin.DEVELOPMENT_SYNTHETIC,
            trust_level=TrustLevel.VALIDATED_LEARNING,
            review_state=LearningCaseReviewState.OBSERVED,
            sanitized=True,
            owner_principal_id=principal.id,
            root_cause_class="retrieval_failure",
        )
    )
    store.upsert_learning_case(case.to_store_dict())
    candidate = generate_improvement_candidate(case)
    if candidate is None:
        raise HTTPException(status_code=500, detail="Candidate generation failed")
    family = family_for_payload_delta(candidate.policy_delta) or PolicyFamily.RETRIEVAL
    baseline = merge_baseline(family)
    experiment = run_experiment(
        case_id=case.case_id,
        baseline_policy=baseline,
        candidate=candidate,
        fixture={"failure_class": "retrieval_failure", "baseline_quality": 0.72},
    )
    cooldown = store.promotion_cooldown_active(
        policy_key=policy_key_for(family), owner_principal_id=principal.id
    )
    decision = evaluate_promotion(
        candidate, experiment, human_approved=True, sample_count=2, cooldown_active=cooldown
    )
    if decision.verdict != PromotionVerdict.SAFE_TO_PROMOTE:
        return {
            "status": decision.verdict.value,
            "classification": "controlled_api_smoke",
            "outcome": experiment.outcome.value,
        }
    promoted = apply_promotion(
        decision,
        candidate.policy_delta,
        owner_principal_id=principal.id,
        policy_family=family,
    )
    if promoted is None:
        raise HTTPException(status_code=500, detail="Promotion failed")
    key = promoted.policy_key
    store.promote_learning_policy(
        policy_key=key,
        version_label=promoted.version_label,
        payload=promoted.payload,
        owner_principal_id=principal.id,
        promoted_from_candidate_id=None,
        promotion_reason=promoted.promotion_reason,
        evidence={"smoke": "controlled_api_smoke"},
        policy_family=family.value,
        scope_key="tenant",
        actor_principal_id=principal.id,
        actor_label="api_smoke",
    )
    store._session.commit()
    return {
        "status": "promoted",
        "classification": "controlled_api_smoke",
        "policy_key": key,
        "version": promoted.version_label,
    }
