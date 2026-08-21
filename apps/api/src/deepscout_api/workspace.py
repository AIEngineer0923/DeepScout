"""Composite read models for the product frontend — domain state remains authoritative."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from deepscout_evaluation.registry import BUILTIN_EVALUATOR_MATRIX
from deepscout_evaluation.run_evals import evaluate_research_run
from deepscout_persistence.store import ResearchStore


def worker_display_name(index: int, objective: str) -> str:
    words = [token.strip(".,:;()") for token in objective.split() if token.strip(".,:;()")]
    label = " ".join(words[:4]) or f"Task {index}"
    return f"W{index:02d} · {label}"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _task_index_map(tasks: list) -> dict[str, int]:
    return {task.task_key: index + 1 for index, task in enumerate(tasks)}


def assemble_workspace(store: ResearchStore, run_id: UUID) -> dict:
    run = store.get_run(run_id)
    if run is None:
        raise LookupError("run not found")
    row = store.get_run_row(run_id)
    usage = store.get_usage_summary(run_id)
    consumption = store.get_consumption(run_id)
    tasks = store.list_tasks(run_id)
    sources = store.list_sources(run_id)
    claims = store.list_claims(run_id)
    evidence = store.list_evidence(run_id)
    contradictions = store.list_contradictions(run_id)
    snapshots = store.list_snapshots_for_run(run_id)
    tools = store.list_tool_executions(run_id)
    jobs = store.list_jobs_for_run(run_id)
    events = store.list_run_events(run_id)
    report = store.get_report(run_id)
    candidates = store.list_search_candidates(run_id)

    completed_phases: list[str] = []
    phase_timings: dict[str, str] = {}
    for event in events:
        if event.event_type != "phase.completed":
            continue
        phase = (event.payload or {}).get("phase")
        if isinstance(phase, str) and phase not in completed_phases:
            completed_phases.append(phase)
        duration = (event.payload or {}).get("duration_s")
        if isinstance(phase, str) and duration is not None:
            phase_timings[phase] = str(duration)

    task_by_id = {str(task.id): task for task in tasks}
    indexes = _task_index_map(tasks)
    question_to_task = {
        str(task.question_id): task for task in tasks if task.question_id is not None
    }

    workers = []
    for index, task in enumerate(tasks, start=1):
        worker_id = str(task.worker_id) if task.worker_id else f"task:{task.id}"
        workers.append(
            {
                "index": index,
                "display_name": worker_display_name(index, task.objective),
                "worker_id": worker_id,
                "task_id": str(task.id),
                "task_key": task.task_key,
                "role": "research_worker",
                "agent_backed": False,
                "parent": "Research Orchestrator",
                "assigned_task": task.objective,
                "state": task.status.value,
                "started_at": _iso(task.started_at),
                "completed_at": _iso(task.completed_at),
                "allowed_tools": task.allowed_tools,
                "source_count": 0,
                "snapshot_count": 0,
                "evidence_count": 0,
                "retries": task.retry_count,
                "skills": [],
            }
        )
    bindings = []
    if hasattr(store, "list_skill_bindings"):
        bindings = store.list_skill_bindings(run_id)
    skills_by_task: dict[str, list[str]] = {}
    for binding in bindings:
        key = str(binding.research_task_id) if binding.research_task_id else "_run"
        skills_by_task.setdefault(key, []).append(binding.skill_id)
    for worker in workers:
        worker["skills"] = skills_by_task.get(worker["task_id"], skills_by_task.get("_run", []))

    snapshot_by_source = {}
    for snapshot in snapshots:
        snapshot_by_source.setdefault(str(snapshot.source_id), []).append(snapshot)

    evidence_by_claim = {}
    evidence_by_snapshot = {}
    for item in evidence:
        evidence_by_claim.setdefault(str(item.claim_id), []).append(item)
        evidence_by_snapshot.setdefault(str(item.snapshot_id), []).append(item)

    claims_by_source = {}
    for claim in claims:
        if claim.source_id:
            claims_by_source.setdefault(str(claim.source_id), []).append(claim)

    source_payloads = []
    for source in sources:
        source_snaps = snapshot_by_source.get(str(source.id), [])
        source_claims = claims_by_source.get(str(source.id), [])
        related_evidence = []
        for claim in source_claims:
            related_evidence.extend(evidence_by_claim.get(str(claim.id), []))
        discovering_task = None
        for candidate in candidates:
            if candidate.url == source.canonical_url and candidate.question_id:
                discovering_task = question_to_task.get(str(candidate.question_id))
                if discovering_task:
                    break
        fetch_state = "fetched" if source_snaps else "discovered"
        source_payloads.append(
            {
                "id": str(source.id),
                "title": source.title or source.domain or source.canonical_url,
                "url": source.canonical_url,
                "domain": source.domain,
                "source_type": source.source_type.value,
                "created_at": _iso(source.created_at),
                "fetch_state": fetch_state,
                "snapshot_available": bool(source_snaps),
                "snapshot_id": str(source_snaps[0].id) if source_snaps else None,
                "claim_count": len(source_claims),
                "evidence_count": len(related_evidence),
                "task_id": str(discovering_task.id) if discovering_task else None,
                "task_key": discovering_task.task_key if discovering_task else None,
                "worker_index": indexes.get(discovering_task.task_key) if discovering_task else None,
            }
        )

    claim_payloads = []
    for claim in claims:
        items = evidence_by_claim.get(str(claim.id), [])
        task = question_to_task.get(str(claim.question_id)) if claim.question_id else None
        unique_sources = {str(claim.source_id)} if claim.source_id else set()
        for item in items:
            snap = next((row for row in snapshots if row.id == item.snapshot_id), None)
            if snap is not None:
                unique_sources.add(str(snap.source_id))
        claim_payloads.append(
            {
                "id": str(claim.id),
                "statement": claim.statement,
                "verification_status": claim.verification_status.value,
                "source_id": str(claim.source_id) if claim.source_id else None,
                "task_id": str(task.id) if task else None,
                "task_key": task.task_key if task else None,
                "worker_index": indexes.get(task.task_key) if task else None,
                "evidence_count": len(items),
                "independent_source_count": len(unique_sources),
                "created_at": _iso(claim.created_at),
            }
        )

    evidence_payloads = []
    for item in evidence:
        snap = next((row for row in snapshots if row.id == item.snapshot_id), None)
        source_id = str(snap.source_id) if snap is not None else None
        evidence_payloads.append(
            {
                "id": str(item.id),
                "claim_id": str(item.claim_id),
                "quote": item.quote,
                "locator": item.locator,
                "snapshot_id": str(item.snapshot_id),
                "source_id": source_id,
                "created_at": _iso(item.created_at),
            }
        )

    contradiction_payloads = []
    for row_c in contradictions:
        contradiction_payloads.append(
            {
                "id": str(row_c.id),
                "description": row_c.description,
                "evidence_status": row_c.evidence_status.value,
                "claim_a_id": str(row_c.claim_a_id),
                "claim_b_id": str(row_c.claim_b_id),
                "created_at": _iso(row_c.created_at),
            }
        )

    snapshot_payloads = []
    for snapshot in snapshots:
        source = next((item for item in sources if item.id == snapshot.source_id), None)
        related = evidence_by_snapshot.get(str(snapshot.id), [])
        snapshot_payloads.append(
            {
                "id": str(snapshot.id),
                "source_id": str(snapshot.source_id),
                "source_title": source.title if source else "",
                "url": source.canonical_url if source else "",
                "retrieved_at": _iso(snapshot.retrieved_at),
                "mime_type": snapshot.mime_type,
                "byte_size": snapshot.byte_size,
                "content_hash": snapshot.content_hash,
                "word_count": len(snapshot.content_text.split()) if snapshot.content_text else 0,
                "evidence_count": len(related),
                "indexing_status": snapshot.indexing_status.value,
                "chunk_count": snapshot.chunk_count,
                "embedding_count": snapshot.embedding_count,
                "indexed_at": _iso(snapshot.indexed_at),
            }
        )

    activity = []
    for event in events[-40:]:
        activity.append(
            {
                "sequence": event.sequence,
                "type": event.event_type,
                "payload": event.payload or {},
                "created_at": _iso(event.created_at),
            }
        )

    evals = evaluate_research_run(store, run_id)
    eval_rows = []
    for spec in BUILTIN_EVALUATOR_MATRIX:
        value = evals.get(spec.evaluator_id)
        if spec.evaluator_id == "citation_correctness":
            value = evals.get("citation_resolve_rate")
        if spec.evaluator_id == "provenance_complete":
            value = evals.get("provenance_complete_rate")
        if spec.evaluator_id == "dag_cycle_free":
            value = evals.get("dag_cycle_free")
        if spec.evaluator_id == "termination_correctness":
            value = evals.get("termination_correct")
        eval_rows.append(
            {
                "evaluator_id": spec.evaluator_id,
                "version": spec.version,
                "category": spec.category,
                "method": spec.method.value,
                "applicability": spec.applicability.value,
                "description": spec.description,
                "value": value,
            }
        )

    completed_tasks = [task for task in tasks if task.status.value == "completed"]
    remaining_tasks = [
        task for task in tasks if task.status.value not in {"completed", "cancelled", "failed"}
    ]
    latest_job = jobs[0] if jobs else None

    return {
        "run_id": str(run.id),
        "status": run.status.value,
        "goal": run.goal,
        "termination_reason": run.termination_reason,
        "llm_provider": run.llm_provider,
        "llm_model": run.llm_model,
        "research_mode": run.research_mode,
        "output_language": run.output_language,
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
        "budget": {
            "max_iterations": run.budget.max_iterations,
            "max_sources": run.budget.max_sources,
            "max_tool_calls": run.budget.max_tool_calls,
            "max_total_tokens": run.budget.max_total_tokens,
            "max_cost_usd": run.budget.max_cost_usd,
            "concurrency_limit": row.concurrency_limit if row else 3,
        },
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cached_input_tokens": usage.cached_input_tokens,
            "reasoning_tokens": usage.reasoning_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": usage.cost_usd,
            "usage_status": usage.usage_status.value,
            "cost_status": usage.cost_status.value,
            "pricing_version": usage.pricing_version,
            "evaluation_total_tokens": usage.evaluation_total_tokens,
            "evaluation_cost_usd": usage.evaluation_cost_usd,
            "cost_unknown_reason": usage.cost_unknown_reason,
            "by_role": store.get_usage_by_role(run_id),
        },
        "counts": {
            "tasks": len(tasks),
            "sources": len(sources),
            "claims": len(claims),
            "evidence": len(evidence),
            "contradictions": len(contradictions),
            "snapshots": len(snapshots),
            "consumed_sources": consumption.sources,
            "consumed_tool_calls": consumption.tool_calls,
        },
        "completed_phases": completed_phases,
        "phase_timings": phase_timings,
        "report": (
            {
                "id": str(report.id),
                "title": report.title,
                "body_markdown": report.body_markdown,
                "created_at": _iso(report.created_at),
            }
            if report
            else None
        ),
        "tasks": [
            {
                "id": str(task.id),
                "task_key": task.task_key,
                "objective": task.objective,
                "status": task.status.value,
                "priority": task.priority,
                "depends_on": task.depends_on,
                "allowed_tools": task.allowed_tools,
                "worker_id": str(task.worker_id) if task.worker_id else None,
                "index": indexes.get(task.task_key),
                "display_name": worker_display_name(indexes.get(task.task_key, 0), task.objective),
                "started_at": _iso(task.started_at),
                "completed_at": _iso(task.completed_at),
                "retries": task.retry_count,
            }
            for task in tasks
        ],
        "workers": workers,
        "sources": source_payloads,
        "snapshots": snapshot_payloads,
        "claims": claim_payloads,
        "evidence": evidence_payloads,
        "contradictions": contradiction_payloads,
        "activity": activity,
        "tools": [
            {
                "id": str(tool.id),
                "tool_name": tool.tool_name,
                "status": tool.status.value,
                "duration_ms": tool.duration_ms,
                "created_at": _iso(tool.created_at),
            }
            for tool in tools[:80]
        ],
        "evaluations": eval_rows,
        "resume": {
            "domain_authority": "postgresql",
            "checkpoint_role": "langgraph_worker_execution_only",
            "completed_task_count": len(completed_tasks),
            "remaining_task_count": len(remaining_tasks),
            "preserved_sources": len(sources),
            "preserved_evidence": len(evidence),
            "current_phase": completed_phases[-1] if completed_phases else "pending",
            "latest_job_type": latest_job.job_type.value if latest_job else None,
            "latest_job_status": latest_job.status.value if latest_job else None,
            "resumable": run.status.value
            in {"pending", "running", "budget_exhausted", "failed"}
            and run.status.value != "paused"
            or (bool(remaining_tasks) and run.status.value != "paused"),
            "awaiting_review": run.status.value == "paused",
        },
        "runtime": {
            "parent_run_id": str(row.parent_run_id) if row and row.parent_run_id else None,
            "fork_reason": row.fork_reason if row else None,
            "replans_used": int(row.replans_used or 0) if row else 0,
            "config_schema_version": (row.config_snapshot or {}).get("state_schema_version")
            if row and row.config_snapshot
            else None,
            "max_delegation_depth": (row.config_snapshot or {}).get("max_delegation_depth")
            if row and row.config_snapshot
            else 1,
        },
        "architecture": {
            "orchestrator": {"label": "Research Orchestrator", "kind": "deterministic"},
            "planner": {"label": "Planner Agent", "kind": "llm_agent"},
            "workers": {"label": "Research Workers", "kind": "langgraph_search"},
            "extraction": {"label": "Extraction Engine", "kind": "deterministic"},
            "verification": {"label": "Verification Engine", "kind": "deterministic"},
            "quality": {"label": "Quality Critic", "kind": "deterministic"},
            "synthesis": {"label": "Synthesis Agent", "kind": "llm_agent"},
            "report": {"label": "Report Engine", "kind": "llm_agent"},
        },
        "_task_by_id": {key: str(value.id) for key, value in task_by_id.items()},
    }


def snapshot_detail(store: ResearchStore, run_id: UUID, snapshot_id: UUID) -> dict:
    workspace = assemble_workspace(store, run_id)
    snapshot = store.get_snapshot(snapshot_id)
    if snapshot is None:
        raise LookupError("snapshot not found")
    source = next((item for item in store.list_sources(run_id) if item.id == snapshot.source_id), None)
    if source is None or source.research_run_id != run_id:
        raise LookupError("snapshot not in run")
    related_claims = [
        claim for claim in workspace["claims"] if claim["source_id"] == str(source.id)
    ]
    related_evidence = [
        item for item in workspace["evidence"] if item["snapshot_id"] == str(snapshot.id)
    ]
    return {
        "run_id": str(run_id),
        "snapshot": {
            "id": str(snapshot.id),
            "source_id": str(snapshot.source_id),
            "retrieved_at": _iso(snapshot.retrieved_at),
            "mime_type": snapshot.mime_type,
            "byte_size": snapshot.byte_size,
            "content_hash": snapshot.content_hash,
            "content_text": snapshot.content_text,
            "source_title": source.title,
            "url": source.canonical_url,
        },
        "claims": related_claims,
        "evidence": related_evidence,
        "source": next(
            (item for item in workspace["sources"] if item["id"] == str(source.id)), None
        ),
    }
