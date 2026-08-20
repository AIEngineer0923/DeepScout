import json
from uuid import UUID

from deepscout_core.domain.schemas import ResearchRunCreate, ResearchRunRead
from deepscout_core.settings import Settings, get_settings
from deepscout_research.jobs.service import JobService
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from deepscout_api.deps import get_research_store

router = APIRouter(prefix="/api/v1/research-runs", tags=["research-runs"])


class ExecuteResponse(BaseModel):
    run_id: UUID
    status: str
    job_id: UUID | None = None


class RunSummaryResponse(BaseModel):
    run_id: UUID
    status: str
    goal: str
    termination_reason: str | None = None
    task_count: int
    source_count: int
    claim_count: int
    evidence_count: int
    contradiction_count: int
    consumed_sources: int
    consumed_tool_calls: int
    total_tokens: int | None = None
    cost_usd: float | None = None
    usage_status: str
    cost_status: str


@router.post("", response_model=ResearchRunRead, status_code=201)
def create_research_run(
    body: ResearchRunCreate,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> ResearchRunRead:
    return store.create_run(body, settings)


@router.get("/{run_id}", response_model=ResearchRunRead)
def get_research_run(
    run_id: UUID,
    store=Depends(get_research_store),
) -> ResearchRunRead:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    return run


@router.get("/{run_id}/events")
def stream_run_events(run_id: UUID, store=Depends(get_research_store)):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")

    def event_generator():
        last_sequence = 0
        while True:
            events = store.list_run_events(run_id, after_sequence=last_sequence)
            for event in events:
                last_sequence = event.sequence
                payload = {
                    "sequence": event.sequence,
                    "type": event.event_type,
                    "payload": event.payload,
                    "created_at": event.created_at.isoformat(),
                }
                yield f"data: {json.dumps(payload)}\n\n"
            if events:
                continue
            run_state = store.get_run(run_id)
            if run_state and run_state.status.value in {
                "completed",
                "failed",
                "cancelled",
                "budget_exhausted",
            }:
                break
            import time

            time.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{run_id}/summary", response_model=RunSummaryResponse)
def get_research_run_summary(
    run_id: UUID,
    store=Depends(get_research_store),
) -> RunSummaryResponse:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    usage = store.get_usage_summary(run_id)
    consumption = store.get_consumption(run_id)
    return RunSummaryResponse(
        run_id=run.id,
        status=run.status.value,
        goal=run.goal,
        termination_reason=run.termination_reason,
        task_count=len(store.list_tasks(run_id)),
        source_count=len(store.list_sources(run_id)),
        claim_count=len(store.list_claims(run_id)),
        evidence_count=len(store.list_evidence(run_id)),
        contradiction_count=len(store.list_contradictions(run_id)),
        consumed_sources=consumption.sources,
        consumed_tool_calls=consumption.tool_calls,
        total_tokens=usage.total_tokens,
        cost_usd=usage.cost_usd,
        usage_status=usage.usage_status.value,
        cost_status=usage.cost_status.value,
    )


@router.post("/{run_id}/execute", response_model=ExecuteResponse, status_code=202)
def execute_research_run(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> ExecuteResponse:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    jobs = JobService(store)
    job = jobs.enqueue_execute_run(run_id)
    if settings.app_env == "development":
        from deepscout_research.jobs.worker import run_worker

        background_tasks.add_task(run_worker, once=True)
    return ExecuteResponse(run_id=run_id, status="accepted", job_id=job.id)


@router.post("/{run_id}/cancel", response_model=ResearchRunRead)
def cancel_research_run(
    run_id: UUID,
    store=Depends(get_research_store),
) -> ResearchRunRead:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    store.cancel_run(run_id)
    updated = store.get_run(run_id)
    assert updated is not None
    return updated
