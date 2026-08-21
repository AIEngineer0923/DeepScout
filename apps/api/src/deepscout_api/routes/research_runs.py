import asyncio
from datetime import datetime
from uuid import UUID

from deepscout_core.domain.schemas import ResearchRunCreate, ResearchRunRead
from deepscout_core.security.csv import render_csv
from deepscout_core.settings import Settings, get_settings
from deepscout_evaluation.registry import BUILTIN_EVALUATOR_MATRIX
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore, _usage_summary_from_run
from deepscout_research.jobs.service import JobService
from deepscout_research.streaming.notify import NotifyWaiter
from deepscout_research.streaming.policy import layer_for
from deepscout_research.streaming.sse import (
    format_sse_comment,
    format_sse_event,
    parse_last_event_id,
)
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel

from deepscout_api.deps import get_research_store
from deepscout_api.workspace import assemble_workspace, snapshot_detail

router = APIRouter(prefix="/api/v1/research-runs", tags=["research-runs"])


def _snapshot(settings: Settings) -> dict:
    from deepscout_research.runtime.config_snapshot import build_config_snapshot

    return build_config_snapshot(settings)


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
    research_mode: str | None = None
    output_language: str = "en"
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


def _list_item(row, metrics: dict[str, int]) -> RunListItem:
    usage = _usage_summary_from_run(row)
    return RunListItem(
        id=row.id,
        goal=row.goal,
        status=row.status.value,
        llm_provider=row.llm_provider,
        llm_model=row.llm_model,
        research_mode=row.research_mode,
        output_language=row.output_language,
        termination_reason=row.termination_reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        total_tokens=usage.total_tokens,
        cost_usd=usage.cost_usd,
        cost_status=usage.cost_status.value,
        source_count=metrics["source_count"],
        evidence_count=metrics["evidence_count"],
        claim_count=metrics["claim_count"],
        task_count=metrics["task_count"],
        completed_task_count=metrics["completed_task_count"],
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
    return store.create_run(body, settings, config_snapshot=_snapshot(settings))


@router.get("", response_model=None)
def list_research_runs(
    store=Depends(get_research_store),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    format: str | None = Query(default=None),
) -> RunListResponse | PlainTextResponse:
    try:
        rows, total = store.list_runs(status=status, query=q, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    metrics = store.list_run_card_metrics([row.id for row in rows])
    items = [_list_item(row, metrics[row.id]) for row in rows]
    if format == "csv":
        body = render_csv(
            ["id", "goal", "status", "research_mode", "output_language", "tokens", "cost", "updated_at"],
            [
                [
                    item.id,
                    item.goal,
                    item.status,
                    item.research_mode or "",
                    item.output_language,
                    item.total_tokens or "",
                    item.cost_usd or "",
                    item.updated_at.isoformat(),
                ]
                for item in items
            ],
        )
        return PlainTextResponse(
            body,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="research-runs.csv"'},
        )
    return RunListResponse(items=items, total=total, limit=limit, offset=offset)


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
def stream_run_events(
    run_id: UUID,
    request: Request,
    after: int | None = Query(default=None, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    settings: Settings = Depends(get_settings),
):
    factory = get_session_factory(settings.database_url)
    probe = factory()
    try:
        if ResearchStore(probe).get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="Research run not found")
    finally:
        probe.close()

    start_after = parse_last_event_id(last_event_id, after)

    async def event_generator():
        last_sequence = start_after
        terminal = {
            "completed",
            "failed",
            "cancelled",
            "budget_exhausted",
        }
        waiter = NotifyWaiter(settings.database_url)
        try:
            while True:
                if await request.is_disconnected():
                    break
                session = factory()
                try:
                    store = ResearchStore(session)
                    events = store.list_run_events(run_id, after_sequence=last_sequence)
                    payloads = []
                    for event in events:
                        last_sequence = event.sequence
                        payloads.append(
                            format_sse_event(
                                sequence=event.sequence,
                                event_type=event.event_type,
                                payload={
                                    "sequence": event.sequence,
                                    "type": event.event_type,
                                    "layer": layer_for(event.event_type).value,
                                    "payload": event.payload,
                                    "created_at": event.created_at.isoformat(),
                                },
                            )
                        )
                    run_state = store.get_run(run_id)
                    status = run_state.status.value if run_state else "failed"
                finally:
                    session.close()
                for frame in payloads:
                    yield frame
                if payloads:
                    continue
                if status in terminal:
                    break
                yield format_sse_comment()
                timeout = 0.4 if status == "running" else 0.8
                await asyncio.to_thread(waiter.wait, run_id, timeout)
        finally:
            waiter.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
        },
    )


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
    response: Response,
    include_evals: bool | None = Query(default=None),
    store=Depends(get_research_store),
) -> dict:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    payload = assemble_workspace(store, run_id, include_evals=include_evals)
    payload.pop("_task_by_id", None)
    timings = payload.get("timings_ms") or {}
    if timings:
        response.headers["Server-Timing"] = ",".join(
            f"{key};dur={value}" for key, value in timings.items()
        )
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
    if run.status.value == "paused":
        raise HTTPException(
            status_code=409,
            detail="Run is waiting for review — resolve the pending review instead of resume",
        )
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
    created = store.create_run(
        ResearchRunCreate(
            goal=run.goal,
            budget=run.budget,
            research_mode=run.research_mode,
            output_language=run.output_language,
        ),
        settings,
        config_snapshot=_snapshot(settings),
    )
    jobs = JobService(store)
    job = jobs.enqueue_execute_run(created.id)
    _kick_worker(background_tasks, settings)
    return ExecuteResponse(run_id=created.id, status="accepted", job_id=job.id)


class ForkBody(BaseModel):
    reason: str = "operator_fork"


@router.post("/{run_id}/fork", response_model=ExecuteResponse, status_code=202)
def fork_research_run(
    run_id: UUID,
    body: ForkBody,
    background_tasks: BackgroundTasks,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> ExecuteResponse:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    created = store.create_run(
        ResearchRunCreate(
            goal=run.goal,
            budget=run.budget,
            research_mode=run.research_mode,
            output_language=run.output_language,
        ),
        settings,
        config_snapshot=_snapshot(settings),
        parent_run_id=run_id,
        fork_reason=body.reason[:128],
    )
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
    workspace = assemble_workspace(store, run_id, include_evals=True)
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
    format: str = Query(default="markdown", pattern="^(markdown|json|csv|pdf|sources-csv|evals-json|evals-csv|snapshot-text)$"),
    snapshot_id: UUID | None = None,
):
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    workspace = assemble_workspace(store, run_id, include_evals=True)
    workspace.pop("_task_by_id", None)
    if format == "json":
        return workspace
    if format == "evals-json":
        return {"run_id": str(run_id), "evaluations": workspace["evaluations"]}
    if format == "evals-csv":
        body = render_csv(
            ["evaluator_id", "version", "category", "method", "applicability", "value"],
            [
                [
                    item["evaluator_id"],
                    item["version"],
                    item["category"],
                    item["method"],
                    item["applicability"],
                    item.get("value") or "",
                ]
                for item in workspace["evaluations"]
            ],
        )
        return PlainTextResponse(
            body,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="evaluations.csv"'},
        )
    if format == "history-csv":
        raise HTTPException(status_code=400, detail="history-csv is a list export, not a run export")
    if format == "csv" or format == "sources-csv":
        body = render_csv(
            ["title", "domain", "url", "status", "claims", "evidence"],
            [
                [
                    source["title"],
                    source["domain"],
                    source["url"],
                    source["fetch_state"],
                    source["claim_count"],
                    source["evidence_count"],
                ]
                for source in workspace["sources"]
            ],
        )
        return PlainTextResponse(
            body,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="sources.csv"'},
        )
    if format == "snapshot-text":
        if snapshot_id is None:
            raise HTTPException(status_code=400, detail="snapshot_id required")
        detail = snapshot_detail(store, run_id, snapshot_id)
        return PlainTextResponse(detail["snapshot"]["content_text"], media_type="text/plain")
    report = workspace.get("report") or {}
    markdown = report.get("body_markdown") or f"# {workspace['goal']}\n\nReport is not available yet.\n"
    if format == "markdown":
        return PlainTextResponse(
            markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="report.md"'},
        )
    return Response(
        content=_report_pdf(workspace["goal"], markdown),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="report.pdf"'},
    )


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_pdf_line(text: str, width: int = 92) -> list[str]:
    if not text:
        return [""]
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        while len(word) > width:
            lines.append(word[:width])
            word = word[width:]
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def _report_pdf(title: str, body: str) -> bytes:
    """Simple multi-page Helvetica PDF with wrapping, margins, and heading hierarchy."""
    page_width = 612
    page_height = 792
    margin = 54
    y_start = page_height - margin
    line_height = 13
    title_size = 16
    body_size = 11
    heading_size = 13

    pages: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    y = y_start

    def add_line(size: int, text: str) -> None:
        nonlocal y, current
        if y < margin + line_height:
            pages.append(current)
            current = []
            y = y_start
        current.append((size, text))
        y -= 22 if size >= 15 else (18 if size >= 13 else line_height)

    add_line(title_size, title[:180] or "DeepScout report")
    add_line(body_size, "")
    for raw in body.replace("\r", "").split("\n"):
        stripped = raw.strip()
        if stripped.startswith("# "):
            add_line(heading_size, stripped[2:])
            continue
        if stripped.startswith("## "):
            add_line(heading_size, stripped[3:])
            continue
        if stripped.startswith("### "):
            add_line(body_size, stripped[4:])
            continue
        if not stripped:
            add_line(body_size, "")
            continue
        for wrapped in _wrap_pdf_line(stripped, 88):
            add_line(body_size, wrapped)
    if current:
        pages.append(current)

    content_objects: list[bytes] = []
    for page in pages:
        commands = ["BT", f"{margin} {y_start} Td"]
        last_size = 0
        for size, text in page:
            if size != last_size:
                font = "F2" if size >= 13 else "F1"
                commands.append(f"/{font} {size} Tf")
                last_size = size
            commands.append(f"({_pdf_escape(text[:200])}) Tj")
            gap = -22 if size >= 15 else (-18 if size >= 13 else -line_height)
            commands.append(f"0 {gap} Td")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", errors="replace")
        content_objects.append(stream)

    objects: list[bytes] = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
    ]
    page_ids = [4 + index * 2 for index in range(len(content_objects) or 1)]
    if not content_objects:
        content_objects = [b"BT /F1 11 Tf 54 738 Td (Empty report) Tj ET"]
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(
        f"2 0 obj << /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >> endobj\n".encode()
    )
    objects.append(
        b"3 0 obj << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
        b"/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> >> >> endobj\n"
    )
    for index, stream in enumerate(content_objects):
        page_id = 4 + index * 2
        content_id = page_id + 1
        objects.append(
            (
                f"{page_id} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Contents {content_id} 0 R /Resources 3 0 R >> endobj\n"
            ).encode()
        )
        objects.append(
            f"{content_id} 0 obj << /Length {len(stream)} >> stream\n".encode()
            + stream
            + b"\nendstream endobj\n"
        )

    xref_positions: list[int] = []
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
