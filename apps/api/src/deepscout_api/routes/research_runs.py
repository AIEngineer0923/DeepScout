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
                yield f'data: {{"sequence": {event.sequence}, "type": "{event.event_type}"}}\n\n'
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
