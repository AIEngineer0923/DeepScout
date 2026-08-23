"""Bounded coverage-driven corrective research — gap tasks through existing worker architecture."""

from __future__ import annotations

from dataclasses import dataclass

from deepscout_core.domain.budget import BudgetConsumption, ResearchBudget
from deepscout_core.domain.contracts import (
    AnswerRequirement,
    CoverageMap,
    RequirementCoverageStatus,
    ResearchContract,
)
from deepscout_core.domain.research_profiles import research_profile
from deepscout_core.domain.schemas import PlannerTask
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore

from deepscout_research.contracts.coverage import evaluate_coverage, gap_search_queries
from deepscout_research.contracts.extract import contract_from_snapshot
from deepscout_research.contracts.query_planning import (
    gap_queries_for_requirement,
    office_holder_queries,
    query_fingerprint,
)
from deepscout_research.contracts.source_authority import enrich_search_query_with_policy

_GAP_TRIGGER_STATUSES = {
    RequirementCoverageStatus.NOT_RESEARCHED,
    RequirementCoverageStatus.SEARCHED,
    RequirementCoverageStatus.SEARCHED_NO_EVIDENCE,
    RequirementCoverageStatus.PARTIAL,
    RequirementCoverageStatus.UNSUPPORTED,
}

_PRIORITY_ORDER = (
    "R_president",
    "R_reg_now",
    "R_reg_apply",
    "R_reg_later",
    "R_gpai_guidance",
    "R_compare",
    "R0",
    "R_quant",
    "R_dep",
)


@dataclass(frozen=True, slots=True)
class CorrectiveResearchDecision:
    apply: bool
    new_tasks: tuple[PlannerTask, ...]
    reason: str
    coverage: CoverageMap | None = None


def coverage_rounds_used(snapshot: dict | None) -> int:
    if not snapshot:
        return 0
    return int(snapshot.get("coverage_research_rounds") or 0)


def _prioritized_gap_ids(gap_ids: list[str], attempts: dict[str, int] | None = None) -> list[str]:
    attempts = attempts or {}
    priority = {req_id: index for index, req_id in enumerate(_PRIORITY_ORDER)}
    return sorted(
        dict.fromkeys(gap_ids),
        key=lambda req_id: (attempts.get(req_id, 0), priority.get(req_id, len(priority))),
    )


def material_gap_requirement_ids(coverage: CoverageMap, contract: ResearchContract) -> list[str]:
    gaps: list[str] = []
    attempts: dict[str, int] = {}
    req_by_id = {item.requirement_id: item for item in contract.requirements}
    for entry in coverage.entries:
        req = req_by_id.get(entry.requirement_id)
        if req is None or not req.critical or req.materiality != "central":
            continue
        if entry.status in _GAP_TRIGGER_STATUSES:
            gaps.append(entry.requirement_id)
            attempts[entry.requirement_id] = entry.corrective_attempts
    return _prioritized_gap_ids(gaps, attempts)


def is_simple_fast_path(contract: ResearchContract) -> bool:
    if len(contract.requirements) > 3:
        return False
    lowered = contract.primary_question.casefold()
    if any(
        token in lowered
        for token in ("compare", "versus", "regulation", "obligation", "tradeoff", "lifecycle")
    ):
        return False
    return True


def _attempted_fingerprints(snapshot: dict | None) -> set[str]:
    if not snapshot:
        return set()
    raw = snapshot.get("coverage_query_fingerprints") or []
    return {str(item) for item in raw}


def evaluate_corrective_research(
    store: ResearchStore,
    run_id,
    *,
    settings: Settings,
    budget: ResearchBudget,
    consumption: BudgetConsumption,
) -> CorrectiveResearchDecision:
    row = store.get_run_row(run_id)
    snapshot = row.config_snapshot if row else None
    contract = contract_from_snapshot(snapshot)
    if contract is None:
        return CorrectiveResearchDecision(False, (), "no_research_contract")

    coverage = evaluate_coverage(store, run_id, contract)
    rounds_used = coverage_rounds_used(snapshot)
    profile = research_profile(row.research_mode if row else None)
    max_rounds = min(profile.max_coverage_rounds, settings.research_max_coverage_rounds)
    store.merge_config_snapshot(run_id, {"coverage_round_limit": max_rounds})
    if rounds_used >= max_rounds:
        return CorrectiveResearchDecision(False, (), "max_coverage_rounds", coverage=coverage)

    if consumption.is_exhausted(budget):
        return CorrectiveResearchDecision(False, (), "budget_exhausted", coverage=coverage)

    remaining_tools = budget.max_tool_calls - consumption.tool_calls
    if remaining_tools < 1:
        return CorrectiveResearchDecision(False, (), "no_tool_budget", coverage=coverage)

    gap_ids = material_gap_requirement_ids(coverage, contract)
    if not gap_ids:
        return CorrectiveResearchDecision(False, (), "no_material_gaps", coverage=coverage)

    if is_simple_fast_path(contract) and any(
        entry.status == RequirementCoverageStatus.SUPPORTED for entry in coverage.entries
    ):
        return CorrectiveResearchDecision(False, (), "simple_path_sufficient", coverage=coverage)

    existing_keys = {task.task_key for task in store.list_tasks(run_id)}
    existing_objectives = {task.objective.strip().casefold() for task in store.list_tasks(run_id)}
    attempted = _attempted_fingerprints(snapshot)
    additions: list[PlannerTask] = []
    new_fingerprints: list[str] = []
    limit = min(profile.gap_queries_per_round, settings.research_max_gap_queries_per_round)
    try:
        from deepscout_evaluation.learning.policy_runtime import corrective_gap_queries_bonus

        owner_id = row.owner_principal_id if row else None
        limit += corrective_gap_queries_bonus(store, owner_principal_id=owner_id)
    except Exception:
        pass
    req_by_id = {item.requirement_id: item for item in contract.requirements}
    query_sets: list[tuple[str, AnswerRequirement, list[str]]] = []
    for req_id in gap_ids:
        req = req_by_id.get(req_id)
        if req is None:
            continue
        if req_id == "R_president":
            candidate_queries = office_holder_queries(contract)
        else:
            candidate_queries = gap_queries_for_requirement(
                req,
                contract,
                round_number=rounds_used + 1,
            )
        query_sets.append((req_id, req, candidate_queries))

    max_variants = max((len(item[2]) for item in query_sets), default=0)
    for variant_index in range(max_variants):
        for req_id, req, candidate_queries in query_sets:
            if variant_index >= len(candidate_queries):
                continue
            query = candidate_queries[variant_index]
            enriched = enrich_search_query_with_policy(query, contract)
            fingerprint = query_fingerprint(enriched)
            if fingerprint in attempted:
                continue
            key = f"gap_r{rounds_used + 1}_{req_id.lower().replace('_', '-')}"[:64]
            if key in existing_keys or enriched.casefold() in existing_objectives:
                continue
            additions.append(
                PlannerTask(
                    task_key=f"{key}-{len(additions) + 1}"[:64],
                    objective=enriched[:500],
                    question_text=req.text[:500],
                    depends_on=[],
                    priority=min(5, 1 + rounds_used),
                    dependency_reason=f"coverage_gap:{req_id}",
                )
            )
            new_fingerprints.append(fingerprint)
            if len(additions) >= limit:
                break
        if len(additions) >= limit:
            break

    if not additions:
        fallback = gap_search_queries(contract, coverage, limit=limit)
        for index, query in enumerate(fallback):
            enriched = enrich_search_query_with_policy(query, contract)
            fingerprint = query_fingerprint(enriched)
            if fingerprint in attempted:
                continue
            key = f"gap_r{rounds_used + 1}_q{index + 1}"[:64]
            if key in existing_keys or enriched.casefold() in existing_objectives:
                continue
            additions.append(
                PlannerTask(
                    task_key=key,
                    objective=enriched[:500],
                    question_text=query[:500],
                    depends_on=[],
                    priority=min(5, 2 + rounds_used),
                    dependency_reason="coverage_gap:fallback",
                )
            )
            new_fingerprints.append(fingerprint)
    if not additions:
        return CorrectiveResearchDecision(False, (), "duplicate_gap_tasks", coverage=coverage)
    if new_fingerprints:
        store.merge_config_snapshot(
            run_id,
            {"coverage_query_fingerprints": list(attempted | set(new_fingerprints))[:50]},
        )
    return CorrectiveResearchDecision(
        True,
        tuple(additions),
        "material_coverage_gaps",
        coverage=coverage,
    )


def record_coverage_attempt(
    store: ResearchStore,
    run_id,
    *,
    coverage: CoverageMap,
    tasks: list[PlannerTask],
    round_number: int,
) -> None:
    row = store.get_run_row(run_id)
    snapshot = (row.config_snapshot if row else None) or {}
    target_requirement_ids = {
        task.dependency_reason.split(":", 1)[1]
        for task in tasks
        if task.dependency_reason.startswith("coverage_gap:")
        and task.dependency_reason != "coverage_gap:fallback"
    }
    attempts = list(snapshot.get("coverage_gap_attempts") or [])
    for entry in coverage.entries:
        if (
            entry.status in _GAP_TRIGGER_STATUSES
            and entry.requirement_id in target_requirement_ids
        ):
            attempts.append(
                {
                    "round": round_number,
                    "requirement_id": entry.requirement_id,
                    "status": entry.status.value,
                    "note": entry.note,
                }
            )
    trace = list(snapshot.get("coverage_query_trace") or [])
    for task in tasks[:10]:
        reason = task.dependency_reason or ""
        requirement_id = reason.split(":", 1)[1] if reason.startswith("coverage_gap:") else ""
        trace.append(
            {
                "round": round_number,
                "requirement_id": requirement_id,
                "query": task.objective[:300],
                "fingerprint": query_fingerprint(task.objective),
            }
        )
    queries = [task.objective for task in tasks]
    store.merge_config_snapshot(
        run_id,
        {
            "coverage_research_rounds": round_number,
            "coverage_map": coverage.model_dump(mode="json"),
            "coverage_gap_attempts": attempts[-50:],
            "coverage_gap_queries": queries[:10],
            "coverage_query_trace": trace[-50:],
        },
    )
