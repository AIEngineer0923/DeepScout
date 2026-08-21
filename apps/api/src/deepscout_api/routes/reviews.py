"""Operational HITL review APIs and human evaluation feedback."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_core.domain.enums import HumanFeedbackTarget, ReviewDecisionKind, ReviewRequestStatus
from deepscout_core.settings import Settings, get_settings
from deepscout_research.hitl import LOCAL_OPERATOR, HumanReviewService
from deepscout_research.jobs.service import JobService
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from deepscout_api.deps import get_research_store

router = APIRouter(tags=["reviews"])


def _kick_worker(background_tasks: BackgroundTasks, settings: Settings) -> None:
    if settings.app_env == "development":
        from deepscout_research.jobs.worker import run_worker

        background_tasks.add_task(run_worker, once=True)


class ReviewRead(BaseModel):
    id: UUID
    research_run_id: UUID
    reason_code: str
    risk_level: str
    title: str
    explanation: str
    proposed_action_type: str
    proposed_action_payload: dict[str, Any]
    payload_hash: str
    status: str
    version: int
    created_at: Any
    expires_at: Any | None
    resolved_at: Any | None
    decision_kind: str | None
    decision_reason: str | None


class ApproveBody(BaseModel):
    reason: str | None = None


class EditBody(BaseModel):
    requested_extra_iterations: int = Field(ge=0, le=20)
    requested_extra_tool_calls: int = Field(ge=0, le=100)
    requested_extra_sources: int = Field(ge=0, le=50)
    reason: str | None = None


class RejectBody(BaseModel):
    outcome: str = "STOP_AND_SYNTHESIZE"
    reason: str | None = None


class RespondBody(BaseModel):
    response: str = Field(min_length=1, max_length=8000)
    reason: str | None = None


class FeedbackBody(BaseModel):
    target_type: HumanFeedbackTarget = HumanFeedbackTarget.OVERALL
    scores: dict[str, int] = Field(default_factory=dict)
    note: str | None = Field(default=None, max_length=4000)
    target_id: UUID | None = None


def _to_read(row) -> ReviewRead:  # noqa: ANN001
    return ReviewRead(
        id=row.id,
        research_run_id=row.research_run_id,
        reason_code=row.reason_code.value,
        risk_level=row.risk_level.value,
        title=row.title,
        explanation=row.explanation,
        proposed_action_type=row.proposed_action_type,
        proposed_action_payload=dict(row.proposed_action_payload or {}),
        payload_hash=row.payload_hash,
        status=row.status.value,
        version=row.version,
        created_at=row.created_at,
        expires_at=row.expires_at,
        resolved_at=row.resolved_at,
        decision_kind=row.decision_kind.value if row.decision_kind else None,
        decision_reason=row.decision_reason,
    )


@router.get("/api/v1/reviews", response_model=list[ReviewRead])
def list_reviews(
    status: str | None = "pending",
    store=Depends(get_research_store),
) -> list[ReviewRead]:
    st = ReviewRequestStatus(status) if status else None
    return [_to_read(row) for row in store.list_reviews(status=st)]


@router.get("/api/v1/research-runs/{run_id}/reviews", response_model=list[ReviewRead])
def list_run_reviews(run_id: UUID, store=Depends(get_research_store)) -> list[ReviewRead]:
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    return [_to_read(row) for row in store.list_reviews(run_id=run_id)]


@router.get("/api/v1/research-runs/{run_id}/reviews/{review_id}", response_model=ReviewRead)
def get_review(run_id: UUID, review_id: UUID, store=Depends(get_research_store)) -> ReviewRead:
    row = store.get_review_request(review_id)
    if row is None or row.research_run_id != run_id:
        raise HTTPException(status_code=404, detail="Review not found")
    return _to_read(row)


def _resolve_and_maybe_resume(
    *,
    run_id: UUID,
    review_id: UUID,
    decision_kind: ReviewDecisionKind,
    body_payload: dict[str, Any] | None,
    reason: str | None,
    rejection_outcome: str | None,
    background_tasks: BackgroundTasks,
    store,
    settings: Settings,
) -> dict[str, Any]:
    service = HumanReviewService(store, settings)
    try:
        result = service.resolve_review(
            run_id=run_id,
            review_id=review_id,
            decision_kind=decision_kind,
            source="api",
            identity=LOCAL_OPERATOR,
            decision_payload=body_payload,
            decision_reason=reason,
            rejection_outcome=rejection_outcome or "STOP_AND_SYNTHESIZE",
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    job_id = None
    if result.run_status.value == "pending" and result.applied:
        jobs = JobService(store)
        job = jobs.enqueue_resume_run(run_id)
        _kick_worker(background_tasks, settings)
        job_id = job.id
        store.append_review_event(
            review_id,
            run_id,
            event_type="resume_started",
            actor_source="api",
            actor_identity=LOCAL_OPERATOR,
            detail={"job_id": str(job_id)},
        )
    return {
        "review_id": str(result.review_id),
        "status": result.status.value,
        "run_status": result.run_status.value,
        "applied": result.applied,
        "job_id": str(job_id) if job_id else None,
    }


@router.post("/api/v1/research-runs/{run_id}/reviews/{review_id}/approve")
def approve_review(
    run_id: UUID,
    review_id: UUID,
    body: ApproveBody,
    background_tasks: BackgroundTasks,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return _resolve_and_maybe_resume(
        run_id=run_id,
        review_id=review_id,
        decision_kind=ReviewDecisionKind.APPROVE,
        body_payload=None,
        reason=body.reason,
        rejection_outcome=None,
        background_tasks=background_tasks,
        store=store,
        settings=settings,
    )


@router.post("/api/v1/research-runs/{run_id}/reviews/{review_id}/edit")
def edit_review(
    run_id: UUID,
    review_id: UUID,
    body: EditBody,
    background_tasks: BackgroundTasks,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return _resolve_and_maybe_resume(
        run_id=run_id,
        review_id=review_id,
        decision_kind=ReviewDecisionKind.EDIT,
        body_payload={
            "requested_extra_iterations": body.requested_extra_iterations,
            "requested_extra_tool_calls": body.requested_extra_tool_calls,
            "requested_extra_sources": body.requested_extra_sources,
        },
        reason=body.reason,
        rejection_outcome=None,
        background_tasks=background_tasks,
        store=store,
        settings=settings,
    )


@router.post("/api/v1/research-runs/{run_id}/reviews/{review_id}/reject")
def reject_review(
    run_id: UUID,
    review_id: UUID,
    body: RejectBody,
    background_tasks: BackgroundTasks,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return _resolve_and_maybe_resume(
        run_id=run_id,
        review_id=review_id,
        decision_kind=ReviewDecisionKind.REJECT,
        body_payload=None,
        reason=body.reason,
        rejection_outcome=body.outcome,
        background_tasks=background_tasks,
        store=store,
        settings=settings,
    )


@router.post("/api/v1/research-runs/{run_id}/reviews/{review_id}/respond")
def respond_review(
    run_id: UUID,
    review_id: UUID,
    body: RespondBody,
    background_tasks: BackgroundTasks,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return _resolve_and_maybe_resume(
        run_id=run_id,
        review_id=review_id,
        decision_kind=ReviewDecisionKind.RESPOND,
        body_payload={"response": body.response},
        reason=body.reason,
        rejection_outcome=None,
        background_tasks=background_tasks,
        store=store,
        settings=settings,
    )


@router.post("/api/v1/research-runs/{run_id}/feedback")
def create_feedback(
    run_id: UUID,
    body: FeedbackBody,
    store=Depends(get_research_store),
) -> dict[str, str]:
    """Human evaluation only — cannot authorize operational reviews."""
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    try:
        feedback_id = store.create_human_feedback(
            research_run_id=run_id,
            target_type=body.target_type,
            scores=body.scores,
            note=body.note,
            target_id=body.target_id,
            source="ui",
            created_by=LOCAL_OPERATOR,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"id": str(feedback_id), "namespace": "evaluation"}
