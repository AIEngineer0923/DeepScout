"""Execute DeepScout deterministic evaluators against persisted run artifacts."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.contracts import (
    CoverageGapCause,
    FinalCriticResult,
    FinalCriticVerdict,
    RequirementCoverageStatus,
    RequirementKind,
)
from deepscout_core.domain.enums import ResearchRunStatus
from deepscout_core.domain.schemas import WORKER_TOOL_ALLOWLIST
from deepscout_persistence.store import ResearchStore
from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.extract import contract_from_snapshot
from deepscout_research.tasks.graph import TaskGraph, TaskGraphError

from deepscout_evaluation.deterministic import (
    eval_budget_compliance,
    eval_claim_has_evidence,
    eval_duplicate_work,
    eval_provenance_complete,
    eval_quote_resolves,
    eval_termination_correct,
    eval_unsupported_claim_rate,
)
from deepscout_evaluation.retrieval_metrics import duplicate_candidate_rate
from deepscout_evaluation.security_evals import (
    eval_code_injection_texts,
    eval_pii_leakage_texts,
    eval_prompt_injection_texts,
    eval_secret_leakage_texts,
    eval_ssrf_urls,
)
from deepscout_evaluation.trajectory import (
    REQUIRED_MULTI_AGENT_ACTIONS,
    TrajectoryMatchMode,
    actions_from_run_events,
    match_trajectory,
)


def evaluate_research_run(store: ResearchStore, run_id: UUID) -> dict[str, object]:
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"ResearchRun {run_id} not found")
    claims = store.list_claims(run_id)
    evidence = store.list_evidence(run_id)
    tasks = store.list_tasks(run_id)
    events = store.list_run_events(run_id)
    consumption = store.get_consumption(run_id)
    sources = store.list_sources(run_id)
    snapshots = store.list_snapshots_for_run(run_id)
    candidates = store.list_search_candidates(run_id)
    tool_executions = store.list_tool_executions(run_id)
    report = store.get_report(run_id)
    row = store.get_run_row(run_id)
    config_snapshot = (row.config_snapshot if row else None) or {}
    contract = contract_from_snapshot(config_snapshot)
    coverage = evaluate_coverage(store, run_id, contract) if contract else None
    coverage_by_id = {
        entry.requirement_id: entry for entry in (coverage.entries if coverage else [])
    }
    central_requirements = [
        item
        for item in (contract.requirements if contract else [])
        if item.materiality == "central" and item.kind != RequirementKind.OUTPUT_FORMAT
    ]
    requirement_coverage = bool(contract) and all(
        coverage_by_id.get(item.requirement_id) is not None
        and coverage_by_id[item.requirement_id].status == RequirementCoverageStatus.SUPPORTED
        for item in central_requirements
    )
    quantitative = [
        item
        for item in central_requirements
        if item.quantification_required or item.kind == RequirementKind.QUANTIFICATION
    ]
    comparisons = [
        item for item in central_requirements if item.kind == RequirementKind.COMPARISON
    ]
    quantitative_coverage = (
        all(
            item.requirement_id in coverage_by_id
            and coverage_by_id[item.requirement_id].status
            == RequirementCoverageStatus.SUPPORTED
            for item in quantitative
        )
        if quantitative
        else None
    )
    comparison_completeness = (
        all(
            item.requirement_id in coverage_by_id
            and coverage_by_id[item.requirement_id].status
            == RequirementCoverageStatus.SUPPORTED
            for item in comparisons
        )
        if comparisons
        else None
    )
    source_portfolio_adequacy = bool(contract) and not any(
        entry.gap_cause == CoverageGapCause.SOURCE_PORTFOLIO_INADEQUATE
        for entry in coverage_by_id.values()
        if entry.requirement_id in {item.requirement_id for item in central_requirements}
    )
    raw_critic = config_snapshot.get("final_critic")
    try:
        final_critic = FinalCriticResult.model_validate(raw_critic) if raw_critic else None
    except Exception:
        final_critic = None
    report_contract_compliance = bool(
        final_critic and final_critic.verdict == FinalCriticVerdict.PASS
    )

    evidence_by_claim = {item.claim_id for item in evidence}
    unsupported = sum(1 for claim in claims if claim.id not in evidence_by_claim)
    quote_ok = 0
    provenance_ok = 0
    for item in evidence:
        snapshot = store.get_snapshot(item.snapshot_id)
        text = snapshot.content_text if snapshot is not None else ""
        if eval_quote_resolves(quote=item.quote, snapshot_text=text):
            quote_ok += 1
        claim = next((row for row in claims if row.id == item.claim_id), None)
        if eval_provenance_complete(
            claim_has_source=claim is not None and claim.source_id is not None,
            evidence_has_snapshot=snapshot is not None,
        ):
            provenance_ok += 1

    dag_ok = True
    try:
        TaskGraph(tasks=tuple(tasks)).validate_dependencies()
    except TaskGraphError:
        dag_ok = False

    event_payloads = [
        {"event_type": event.event_type, "payload": event.payload or {}} for event in events
    ]
    actual_actions = actions_from_run_events(event_payloads)
    trajectory_ok = match_trajectory(
        actual_actions,
        list(REQUIRED_MULTI_AGENT_ACTIONS),
        mode=TrajectoryMatchMode.SUPERSET,
    ) or match_trajectory(
        [action for action in actual_actions if action.startswith("phase.")],
        ["phase.plan", "phase.research", "phase.report"],
        mode=TrajectoryMatchMode.SUPERSET,
    )
    plan_adherence = match_trajectory(
        [action for action in actual_actions if action.startswith("phase.")],
        ["phase.plan", "phase.research", "phase.report"],
        mode=TrajectoryMatchMode.SUPERSET,
    )
    tool_selection = match_trajectory(
        actual_actions,
        ["tool.web_search"],
        mode=TrajectoryMatchMode.SUPERSET,
    )

    unique_keys = len({task.task_key for task in tasks})
    completed = sum(1 for task in tasks if task.status.value == "completed")
    allowed_tools = {
        tool
        for task in tasks
        for tool in task.allowed_tools
        if tool in WORKER_TOOL_ALLOWLIST
    } or set(WORKER_TOOL_ALLOWLIST)
    forbidden_tool_ok = all(item.tool_name in allowed_tools for item in tool_executions)

    scan_texts = [
        report.body_markdown if report is not None else "",
        *(item.quote for item in evidence),
        *(item.output_summary for item in tool_executions),
    ]
    source_urls = [item.canonical_url for item in sources if item.canonical_url]
    unique_hashes = {snapshot.content_hash for snapshot in snapshots if snapshot.content_hash}
    duplicate_rate = duplicate_candidate_rate(
        total=len(candidates),
        unique_snapshots=len(unique_hashes),
    )
    snapshot_ids = {snapshot.id for snapshot in snapshots}
    isolation_ok = all(item.snapshot_id in snapshot_ids for item in evidence)

    results: dict[str, object] = {
        "run_id": str(run_id),
        "claim_has_evidence": eval_claim_has_evidence(evidence_count=len(evidence)),
        "unsupported_claim_rate": eval_unsupported_claim_rate(
            claims_without_evidence=unsupported, total_claims=len(claims)
        ),
        "citation_resolve_rate": (quote_ok / len(evidence)) if evidence else None,
        "provenance_complete_rate": (provenance_ok / len(evidence)) if evidence else None,
        "duplicate_work": eval_duplicate_work(
            unique_task_keys=unique_keys, completed_tasks=completed
        ),
        "budget_compliance": eval_budget_compliance(
            consumed=float(consumption.sources), limit=float(run.budget.max_sources)
        ),
        "dag_cycle_free": dag_ok,
        "termination_correct": (
            requirement_coverage and report_contract_compliance
            if run.status == ResearchRunStatus.COMPLETED
            else eval_termination_correct(
                status=run.status.value,
                allowed={
                    ResearchRunStatus.BUDGET_EXHAUSTED.value,
                    ResearchRunStatus.CANCELLED.value,
                    ResearchRunStatus.FAILED.value,
                },
            )
        ),
        "trajectory_accuracy": trajectory_ok,
        "plan_adherence": plan_adherence,
        "tool_selection": tool_selection,
        "task_completion": (
            run.status == ResearchRunStatus.COMPLETED
            and requirement_coverage
            and report_contract_compliance
        ),
        "requirement_coverage": requirement_coverage,
        "source_portfolio_adequacy": source_portfolio_adequacy,
        "quantitative_coverage": quantitative_coverage,
        "comparison_completeness": comparison_completeness,
        "report_contract_compliance": report_contract_compliance,
        "assertions": report is not None and len(claims) > 0,
        "secret_leakage": eval_secret_leakage_texts(scan_texts),
        "pii_leakage": eval_pii_leakage_texts(scan_texts),
        "code_injection": eval_code_injection_texts(scan_texts),
        "prompt_injection": eval_prompt_injection_texts(scan_texts),
        "ssrf_url": eval_ssrf_urls(source_urls),
        "forbidden_tool": forbidden_tool_ok,
        "retrieval_duplicate_rate": duplicate_rate,
        "retrieval_cross_run_isolation": isolation_ok,
        "task_count": len(tasks),
        "source_count": len(sources),
        "evidence_count": len(evidence),
        "status": run.status.value,
    }
    if not quantitative:
        results["quantitative_coverage__status"] = "not_applicable"
        results["quantitative_coverage__reason"] = "No central quantitative requirement."
    if not comparisons:
        results["comparison_completeness__status"] = "not_applicable"
        results["comparison_completeness__reason"] = "No central comparison requirement."
    return results
