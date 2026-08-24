"""Execute DeepScout deterministic evaluators against persisted run artifacts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from deepscout_core.domain.contracts import (
    CoverageGapCause,
    FinalCriticResult,
    FinalCriticVerdict,
    RequirementCoverageStatus,
    RequirementKind,
    SourceKind,
)
from deepscout_core.domain.enums import ResearchRunStatus
from deepscout_core.domain.schemas import WORKER_TOOL_ALLOWLIST
from deepscout_persistence.store import ResearchStore
from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.extract import contract_from_snapshot
from deepscout_research.contracts.source_authority import classify_source_authority
from deepscout_research.contracts.source_portfolio import source_family
from deepscout_research.language import detect_language, normalize_language_tag
from deepscout_research.source_fabric.strategy import QueryStrategy, plan_source_strategy
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
    comparisons = [item for item in central_requirements if item.kind == RequirementKind.COMPARISON]
    quantitative_coverage = (
        all(
            item.requirement_id in coverage_by_id
            and coverage_by_id[item.requirement_id].status == RequirementCoverageStatus.SUPPORTED
            for item in quantitative
        )
        if quantitative
        else None
    )
    comparison_completeness = (
        all(
            item.requirement_id in coverage_by_id
            and coverage_by_id[item.requirement_id].status == RequirementCoverageStatus.SUPPORTED
            for item in comparisons
        )
        if comparisons
        else None
    )
    source_portfolio_adequacy = (
        bool(contract)
        and bool(sources)
        and not any(
            entry.gap_cause == CoverageGapCause.SOURCE_PORTFOLIO_INADEQUATE
            for entry in coverage_by_id.values()
            if entry.requirement_id in {item.requirement_id for item in central_requirements}
        )
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

    false_completion = any(
        event.event_type == "worker.completed"
        and int((event.payload or {}).get("sources_added") or 0) <= 0
        for event in events
    )
    progress_consistent = not false_completion and not (
        any(task.status.value == "completed" for task in tasks) and not sources
    )
    trajectory_ok = trajectory_ok and progress_consistent
    plan_adherence = plan_adherence and progress_consistent
    tool_selection = tool_selection and bool(sources)

    unique_keys = len({task.task_key for task in tasks})
    completed = sum(1 for task in tasks if task.status.value == "completed")
    allowed_tools = {
        tool for task in tasks for tool in task.allowed_tools if tool in WORKER_TOOL_ALLOWLIST
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
    snapshots_by_source = {item.source_id: item for item in snapshots}
    source_families = {source_family(item.canonical_url) for item in sources if item.canonical_url}
    source_metadata = [
        classify_source_authority(url=item.canonical_url, title=item.title or "")
        for item in sources
    ]
    source_kinds = {item.source_kind for item in source_metadata}
    primary_count = sum(item.authority_class.value == "primary" for item in source_metadata)
    strategy = plan_source_strategy(
        run.goal,
        contract,
        research_mode=run.research_mode,
    )
    source_diversity = len(source_kinds) >= strategy.target_source_kinds if sources else False
    source_independence = (
        len(source_families) >= strategy.target_independent_publishers if sources else False
    )
    fetch_success_rate = (len(snapshots_by_source) / len(sources)) if sources else None
    primary_source_ratio = (primary_count / len(sources)) if sources else None
    publisher_duplicate_rate = 1.0 - (len(source_families) / len(sources)) if sources else None
    original_citation_rate = (
        sum(
            not any(
                marker in item.canonical_url
                for marker in ("api.openalex.org", "api.github.com", "tavily.com/search")
            )
            for item in sources
        )
        / len(sources)
        if sources
        else None
    )
    evidence_sources_by_claim: dict[object, set[object]] = {}
    for item in evidence:
        snapshot = store.get_snapshot(item.snapshot_id)
        if snapshot is not None:
            evidence_sources_by_claim.setdefault(item.claim_id, set()).add(snapshot.source_id)
    corroborated = sum(len(source_ids) >= 2 for source_ids in evidence_sources_by_claim.values())
    cross_source_corroboration = (
        corroborated / len(evidence_sources_by_claim) if evidence_sources_by_claim else None
    )
    requested_special_kinds = set(strategy.requested_kinds) - {SourceKind.WEB_PAGE}
    source_type_compliance = (
        bool(source_kinds & requested_special_kinds) if requested_special_kinds else None
    )
    source_dates: list[datetime] = []
    for snapshot in snapshots:
        raw_date = str((snapshot.retrieval_metadata or {}).get("publication_date") or "").strip()
        if not raw_date:
            continue
        try:
            parsed = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except ValueError:
            continue
        source_dates.append(parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC))
    freshness_required = QueryStrategy.RECENT in strategy.query_families
    source_freshness = (
        any(item >= datetime.now(UTC) - timedelta(days=365) for item in source_dates)
        if freshness_required
        else None
    )
    contradictions = store.list_contradictions(run_id)
    contradiction_resolution_rate = (
        sum(item.evidence_status.value == "sufficient" for item in contradictions)
        / len(contradictions)
        if contradictions
        else None
    )
    language_strategy = contract.language_strategy if contract else None
    language_execution = dict(config_snapshot.get("language_execution") or {})
    actual_query_languages = {
        normalize_language_tag(item)
        for item in (language_execution.get("actual_query_languages") or {})
    } - {"und"}
    planned_query_languages = (
        {
            normalize_language_tag(language_strategy.primary_query_language),
            *(
                normalize_language_tag(item)
                for item in language_strategy.additional_query_languages
            ),
        }
        - {"und"}
        if language_strategy
        else set()
    )
    multilingual_applicable = bool(language_strategy and len(planned_query_languages) > 1)
    multilingual_query_coverage = (
        normalize_language_tag(language_strategy.primary_query_language) in actual_query_languages
        and actual_query_languages.issubset(planned_query_languages)
        if multilingual_applicable
        else None
    )
    language_observability_applicable = bool(
        language_execution
        or (
            language_strategy
            and (
                language_strategy.query_variants
                or language_strategy.translation_required
                or language_strategy.expected_primary_source_languages
            )
        )
    )
    snapshot_languages = [
        normalize_language_tag((item.retrieval_metadata or {}).get("original_language"))
        for item in snapshots
    ]
    source_language_metadata = (
        all(item != "und" for item in snapshot_languages)
        if snapshots and language_observability_applicable
        else None
    )
    evidence_original_states = [
        str((item.extraction_metadata or {}).get("translation_state") or "") == "original"
        and normalize_language_tag((item.extraction_metadata or {}).get("original_language"))
        != "und"
        for item in evidence
    ]
    translation_provenance = (
        all(evidence_original_states) if evidence and language_observability_applicable else None
    )
    translation_leakage = (
        translation_provenance and quote_ok == len(evidence)
        if evidence and language_observability_applicable
        else None
    )
    detected_report_language = (
        detect_language(report.body_markdown).language if report is not None else "und"
    )
    requested_output_language = normalize_language_tag(run.output_language)
    output_language_compliance = (
        detected_report_language == requested_output_language
        if report is not None and detected_report_language != "und"
        else None
    )
    cross_language_contradictions = bool(
        contradictions and len(set(snapshot_languages) - {"und"}) > 1
    )
    multilingual_contradiction_handling = (
        contradiction_resolution_rate == 1.0 if cross_language_contradictions else None
    )

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
        # Compatibility alias retained for existing runtime gates and API consumers.
        "budget_sources": eval_budget_compliance(
            consumed=float(consumption.sources), limit=float(run.budget.max_sources)
        ),
        "dag_cycle_free": dag_ok,
        "termination_correct": (
            (requirement_coverage and report_contract_compliance and progress_consistent)
            or (
                run.termination_reason == "completed_with_limitations"
                and bool(evidence)
                and progress_consistent
                and final_critic is not None
                and final_critic.verdict == FinalCriticVerdict.BLOCKED_BY_EVIDENCE
            )
            if run.status == ResearchRunStatus.COMPLETED
            else (
                eval_termination_correct(
                    status=run.status.value,
                    allowed={
                        ResearchRunStatus.BUDGET_EXHAUSTED.value,
                        ResearchRunStatus.CANCELLED.value,
                        ResearchRunStatus.FAILED.value,
                    },
                )
                and (
                    (run.status == ResearchRunStatus.FAILED and "run.failed" in actual_actions)
                    or run.status != ResearchRunStatus.FAILED
                )
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
        "source_diversity": source_diversity,
        "source_independence": source_independence,
        "source_type_compliance": source_type_compliance,
        "source_freshness": source_freshness,
        "primary_source_ratio": primary_source_ratio,
        "source_fetch_success_rate": fetch_success_rate,
        "publisher_duplicate_rate": publisher_duplicate_rate,
        "original_citation_rate": original_citation_rate,
        "cross_source_corroboration": cross_source_corroboration,
        "contradiction_resolution_rate": contradiction_resolution_rate,
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
        "multilingual_query_coverage": multilingual_query_coverage,
        "source_language_metadata": source_language_metadata,
        "translation_provenance": translation_provenance,
        "output_language_compliance": output_language_compliance,
        "translation_leakage": translation_leakage,
        "multilingual_contradiction_handling": multilingual_contradiction_handling,
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
    if not requested_special_kinds:
        results["source_type_compliance__status"] = "not_applicable"
        results["source_type_compliance__reason"] = "No specialized source class was requested."
    if not freshness_required:
        results["source_freshness__status"] = "not_applicable"
        results["source_freshness__reason"] = "The objective is not freshness-sensitive."
    if not contradictions:
        results["contradiction_resolution_rate__status"] = "not_applicable"
        results["contradiction_resolution_rate__reason"] = "No contradiction was detected."
    if not multilingual_applicable:
        results["multilingual_query_coverage__status"] = "not_applicable"
        results["multilingual_query_coverage__reason"] = (
            "The goal-conditioned strategy did not require language expansion."
        )
    if not snapshots or not language_observability_applicable:
        results["source_language_metadata__status"] = "not_applicable"
        results["source_language_metadata__reason"] = (
            "No source snapshot was acquired."
            if not snapshots
            else "This legacy run has no language execution metadata."
        )
    if not evidence or not language_observability_applicable:
        for evaluator_id in ("translation_provenance", "translation_leakage"):
            results[f"{evaluator_id}__status"] = "not_applicable"
            results[f"{evaluator_id}__reason"] = (
                "No evidence quote was admitted."
                if not evidence
                else "This legacy run has no language execution metadata."
            )
    if report is None or detected_report_language == "und":
        results["output_language_compliance__status"] = "unavailable"
        results["output_language_compliance__reason"] = (
            "No report exists or deterministic language detection is inconclusive."
        )
    if not cross_language_contradictions:
        results["multilingual_contradiction_handling__status"] = "not_applicable"
        results["multilingual_contradiction_handling__reason"] = (
            "No contradiction spans multiple detected source languages."
        )
    return results
