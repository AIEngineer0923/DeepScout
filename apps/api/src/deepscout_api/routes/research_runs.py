from uuid import UUID

from deepscout_core.domain.schemas import ResearchRunCreate, ResearchRunRead
from deepscout_core.settings import Settings, get_settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.search.tavily import TavilyWebSearchProvider
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from deepscout_api.deps import get_research_store

router = APIRouter(prefix="/api/v1/research-runs", tags=["research-runs"])


class ExecuteResponse(BaseModel):
    run_id: UUID
    status: str


def _run_orchestrator(run_id: UUID) -> None:
    settings = get_settings()
    session = get_session_factory(settings.database_url)()
    try:
        with TavilyWebSearchProvider(settings) as search_provider:
            orchestrator = ResearchOrchestrator(
                ResearchStore(session),
                settings,
                search_provider,
            )
            orchestrator.execute(run_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("", response_model=ResearchRunRead, status_code=201)
def create_research_run(
    body: ResearchRunCreate,
    store: ResearchStore = Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> ResearchRunRead:
    return store.create_run(body, settings)


@router.get("/{run_id}", response_model=ResearchRunRead)
def get_research_run(
    run_id: UUID,
    store: ResearchStore = Depends(get_research_store),
) -> ResearchRunRead:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    return run


@router.post("/{run_id}/execute", response_model=ExecuteResponse, status_code=202)
def execute_research_run(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    store: ResearchStore = Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> ExecuteResponse:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    background_tasks.add_task(_run_orchestrator, run_id)
    return ExecuteResponse(run_id=run_id, status="accepted")
