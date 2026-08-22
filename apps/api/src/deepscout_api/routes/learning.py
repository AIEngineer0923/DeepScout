"""Learning and self-improvement APIs — owner-scoped, no demo mutation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_core.settings import Settings, get_settings
from deepscout_evaluation.learning.experience_store import (
    list_improvement_candidates_for_owner,
    list_learning_cases_for_owner,
)
from deepscout_evaluation.learning.models import ImprovementCandidateStatus
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
    created_at: Any


class ImprovementCandidateRead(BaseModel):
    id: UUID
    candidate_key: str
    title: str
    status: str
    candidate_type: str
    promotion_verdict: str | None = None
    created_at: Any


class ApproveCandidateBody(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


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
    status: str | None = "requires_human_review",
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> list[ImprovementCandidateRead]:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    rows = list_improvement_candidates_for_owner(store, principal.id, status=status)
    return [ImprovementCandidateRead(**row) for row in rows]


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
    if not store.learning_tables_available():
        raise HTTPException(status_code=503, detail="Learning store unavailable")
    updated = store.update_improvement_candidate_status(
        candidate_id,
        status=ImprovementCandidateStatus.APPROVED.value,
        promotion_verdict="requires_human_review",
        promotion_reason=body.reason or "approved by operator",
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"status": ImprovementCandidateStatus.APPROVED.value}
