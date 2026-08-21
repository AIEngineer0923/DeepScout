"""Research monitors — application-owned schedules. Retrieved text cannot create these."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from deepscout_core.domain.schemas import ResearchMonitorCreate
from deepscout_core.settings import Settings, get_settings
from deepscout_persistence.store import ResearchStore, _monitor_to_read
from deepscout_research.monitors.schedule import compute_next_run_at
from deepscout_research.monitors.service import create_monitor, monitor_status
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deepscout_api.access import authorize_monitor, load_access, owner_for_create
from deepscout_api.deps import get_research_store
from deepscout_api.routes.research_runs import _kick_worker

router = APIRouter(prefix="/api/v1/research-monitors", tags=["monitors"])


class MonitorPatch(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    enabled: bool | None = None
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    weekday: int | None = Field(default=None, ge=0, le=6)
    interval_minutes: int | None = Field(default=None, ge=15, le=10080)
    timezone: str | None = Field(default=None, max_length=64)


def _serialize(store: ResearchStore, row) -> dict:
    running = store.monitor_has_active_run(row.id)
    return _monitor_to_read(row, status=monitor_status(row, child_running=running)).model_dump(
        mode="json"
    )


@router.get("")
def list_monitors(
    request: Request, store=Depends(get_research_store), settings: Settings = Depends(get_settings)
) -> list[dict]:
    access = load_access(request, store._session, settings)
    owner = None if access.is_local else access.principal_id
    if settings.is_hosted() and access.principal is None:
        return []
    return [_serialize(store, row) for row in store.list_monitors(owner_principal_id=owner)]


@router.post("", status_code=201)
def create_monitor_route(
    body: ResearchMonitorCreate,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    access = load_access(request, store._session, settings)
    try:
        row = create_monitor(store, body, owner_principal_id=owner_for_create(access))
        store.commit()
        return _serialize(store, row)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{monitor_id}")
def get_monitor_route(
    monitor_id: UUID,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    access = load_access(request, store._session, settings)
    authorize_monitor(store, monitor_id, access)
    row = store.get_monitor(monitor_id)
    if row is None:
        raise HTTPException(status_code=404, detail="monitor not found")
    history = [
        {"id": str(run.id), "status": run.status.value, "created_at": run.created_at.isoformat()}
        for run in store.list_monitor_runs(monitor_id)
    ]
    payload = _serialize(store, row)
    payload["history"] = history
    return payload


@router.patch("/{monitor_id}")
def patch_monitor(
    monitor_id: UUID,
    body: MonitorPatch,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    access = load_access(request, store._session, settings)
    authorize_monitor(store, monitor_id, access)
    row = store.get_monitor(monitor_id)
    if row is None:
        raise HTTPException(status_code=404, detail="monitor not found")
    if body.name is not None:
        row.name = body.name.strip()
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.hour is not None:
        row.hour = body.hour
    if body.minute is not None:
        row.minute = body.minute
    if body.weekday is not None:
        row.weekday = body.weekday
    if body.interval_minutes is not None:
        row.interval_minutes = body.interval_minutes
    if body.timezone is not None:
        row.timezone = body.timezone
    row.next_run_at = compute_next_run_at(row, after=datetime.now(UTC))
    store.commit()
    return _serialize(store, row)


@router.delete("/{monitor_id}", status_code=204)
def delete_monitor(
    monitor_id: UUID,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> None:
    access = load_access(request, store._session, settings)
    authorize_monitor(store, monitor_id, access)
    row = store.get_monitor(monitor_id)
    if row is None:
        raise HTTPException(status_code=404, detail="monitor not found")
    store._session.delete(row)
    store.commit()


@router.post("/{monitor_id}/run-now", status_code=202)
def run_monitor_now(
    monitor_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    access = load_access(request, store._session, settings)
    authorize_monitor(store, monitor_id, access)
    row = store.get_monitor(monitor_id)
    if row is None:
        raise HTTPException(status_code=404, detail="monitor not found")
    if not row.enabled:
        raise HTTPException(status_code=409, detail="monitor disabled")
    if store.monitor_has_active_run(monitor_id):
        raise HTTPException(status_code=409, detail="monitor already running")
    row.next_run_at = datetime.now(UTC)
    store.commit()
    from deepscout_research.monitors.service import dispatch_due_monitors

    started = dispatch_due_monitors(store, settings, owner="api-run-now")
    store.commit()
    _kick_worker(background_tasks, settings)
    if not started:
        raise HTTPException(status_code=409, detail="monitor did not start")
    return {"run_id": str(started[0]), "monitor_id": str(monitor_id)}
