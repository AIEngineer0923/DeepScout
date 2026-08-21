import json
from datetime import datetime
from uuid import UUID

from deepscout_core.domain.schemas import ResearchRunCreate, ResearchRunRead
from deepscout_core.settings import Settings, get_settings
from deepscout_evaluation.registry import BUILTIN_EVALUATOR_MATRIX
from deepscout_research.jobs.service import JobService
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel

from deepscout_api.deps import get_research_store
from deepscout_api.workspace import assemble_workspace, snapshot_detail

router = APIRouter(prefix="/api/v1/research-runs", tags=["research-runs"])


class ExecuteResponse(BaseModel):
    run_id: UUID
    status: str
    job_id: UUID | None = None


class RunListItem(BaseModel):
    id: UUID
    goal: str
    status: str
    llm_provider: str
    llm_model: str
    termination_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    cost_status: str
    source_count: int
    evidence_count: int
    claim_count: int
    task_count: int
    completed_task_count: int


class RunListResponse(BaseModel):
    items: list[RunListItem]
    total: int
    limit: int
    offset: int


class DashboardResponse(BaseModel):
    active: dict | None
    recent: list[RunListItem]
    totals: dict
    providers: dict
    langsmith: dict


class SettingsStatusResponse(BaseModel):
    identity: dict
    providers: dict
    langsmith: dict
    research_defaults: dict
    health: dict
    model_routing: dict


def _kick_worker(background_tasks: BackgroundTasks, settings: Settings) -> None:
    if settings.app_env == "development":
        from deepscout_research.jobs.worker import run_worker

        background_tasks.add_task(run_worker, once=True)


def _list_item(store, row) -> RunListItem:
    run_id = row.id
    tasks = store.list_tasks(run_id)
    usage = store.get_usage_summary(run_id)
    return RunListItem(
        id=row.id,
        goal=row.goal,
        status=row.status.value,
        llm_provider=row.llm_provider,
        llm_model=row.llm_model,
        termination_reason=row.termination_reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        total_tokens=usage.total_tokens,
        cost_usd=usage.cost_usd,
        cost_status=usage.cost_status.value,
        source_count=len(store.list_sources(run_id)),
        evidence_count=len(store.list_evidence(run_id)),
        claim_count=len(store.list_claims(run_id)),
        task_count=len(tasks),
        completed_task_count=sum(1 for task in tasks if task.status.value == "completed"),
    )


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


class RunWorkspaceResponse(BaseModel):
    run_id: UUID
    status: str
    goal: str
    termination_reason: str | None = None
    llm_provider: str
    llm_model: str
    task_count: int
    source_count: int
    claim_count: int
    evidence_count: int
    contradiction_count: int
    snapshot_count: int
    consumed_sources: int
    consumed_tool_calls: int
    total_tokens: int | None = None
    cost_usd: float | None = None
    usage_status: str
    cost_status: str
    report_available: bool
    report_title: str | None = None
    report_markdown: str | None = None
    tasks: list[dict]
    sources: list[dict]
    claims: list[dict]
    evidence: list[dict]
    contradictions: list[dict]
    completed_phases: list[str]


@router.post("", response_model=ResearchRunRead, status_code=201)
def create_research_run(
    body: ResearchRunCreate,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> ResearchRunRead:
    return store.create_run(body, settings)


@router.get("", response_model=RunListResponse)
def list_research_runs(
    store=Depends(get_research_store),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> RunListResponse:
    try:
        rows, total = store.list_runs(status=status, query=q, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunListResponse(
        items=[_list_item(store, row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


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


@router.get("/{run_id}/workspace")
def get_research_run_workspace(
    run_id: UUID,
    store=Depends(get_research_store),
) -> dict:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    payload = assemble_workspace(store, run_id)
    payload.pop("_task_by_id", None)
    return payload


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


@router.post("/{run_id}/resume", response_model=ExecuteResponse, status_code=202)
def resume_research_run(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> ExecuteResponse:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    if run.status.value in {"completed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Run is terminal and cannot be resumed")
    jobs = JobService(store)
    job = jobs.enqueue_resume_run(run_id)
    _kick_worker(background_tasks, settings)
    return ExecuteResponse(run_id=run_id, status="accepted", job_id=job.id)


@router.post("/{run_id}/restart", response_model=ExecuteResponse, status_code=202)
def restart_research_run(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> ExecuteResponse:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    created = store.create_run(ResearchRunCreate(goal=run.goal, budget=run.budget), settings)
    jobs = JobService(store)
    job = jobs.enqueue_execute_run(created.id)
    _kick_worker(background_tasks, settings)
    return ExecuteResponse(run_id=created.id, status="accepted", job_id=job.id)


@router.get("/{run_id}/snapshots/{snapshot_id}")
def get_snapshot(
    run_id: UUID,
    snapshot_id: UUID,
    store=Depends(get_research_store),
) -> dict:
    try:
        return snapshot_detail(store, run_id, snapshot_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/evaluations")
def get_run_evaluations(
    run_id: UUID,
    store=Depends(get_research_store),
) -> dict:
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    workspace = assemble_workspace(store, run_id)
    return {
        "run_id": str(run_id),
        "evaluations": workspace["evaluations"],
        "usage": workspace["usage"],
        "matrix": [
            {
                "evaluator_id": spec.evaluator_id,
                "category": spec.category,
                "method": spec.method.value,
                "applicability": spec.applicability.value,
                "description": spec.description,
                "version": spec.version,
            }
            for spec in BUILTIN_EVALUATOR_MATRIX
        ],
    }


@router.get("/{run_id}/export")
def export_research_run(
    run_id: UUID,
    store=Depends(get_research_store),
    format: str = Query(default="markdown", pattern="^(markdown|json|csv|pdf|sources-csv|evals-json|snapshot-text)$"),
    snapshot_id: UUID | None = None,
):
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    workspace = assemble_workspace(store, run_id)
    workspace.pop("_task_by_id", None)
    if format == "json":
        return workspace
    if format == "evals-json":
        return {"run_id": str(run_id), "evaluations": workspace["evaluations"]}
    if format == "csv" or format == "sources-csv":
        lines = ["title,domain,url,status,claims,evidence"]
        for source in workspace["sources"]:
            title = source["title"].replace('"', "'")
            lines.append(
                f"\"{title}\",{source['domain']},{source['url']},{source['fetch_state']},"
                f"{source['claim_count']},{source['evidence_count']}"
            )
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/csv")
    if format == "snapshot-text":
        if snapshot_id is None:
            raise HTTPException(status_code=400, detail="snapshot_id required")
        detail = snapshot_detail(store, run_id, snapshot_id)
        return PlainTextResponse(detail["snapshot"]["content_text"], media_type="text/plain")
    report = workspace.get("report") or {}
    markdown = report.get("body_markdown") or f"# {workspace['goal']}\n\nReport is not available yet.\n"
    if format == "markdown":
        return PlainTextResponse(markdown, media_type="text/markdown")
    return Response(content=_simple_pdf(workspace["goal"], markdown), media_type="application/pdf")


def _simple_pdf(title: str, body: str) -> bytes:
    safe_title = title.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:120]
    lines = [line[:90] for line in body.replace("\r", "").split("\n")[:80]]
    stream_lines = ["BT", "/F1 12 Tf", "72 720 Td", f"({safe_title}) Tj", "0 -18 Td"]
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_lines.append(f"({escaped}) Tj")
        stream_lines.append("0 -14 Td")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        b"4 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    xref_positions = []
    output = bytearray(b"%PDF-1.4\n")
    for obj in objects:
        xref_positions.append(len(output))
        output.extend(obj)
    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for pos in xref_positions:
        output.extend(f"{pos:010d} 00000 n \n".encode())
    output.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode()
    )
    return bytes(output)
