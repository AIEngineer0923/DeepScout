"""Requirement-scoped coverage tracking and material gap diagnosis."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from typing import Any

from deepscout_core.domain.budget import BudgetConsumption, ResearchBudget
from deepscout_core.domain.contracts import (
    CoverageGapCause,
    CoverageMap,
    CoverageMapEntry,
    EvidenceType,
    RequirementCoverageStatus,
    RequirementKind,
    ResearchContract,
    SourceClass,
)
from deepscout_core.domain.enums import ClaimVerificationStatus
from deepscout_persistence.store import ResearchStore

from deepscout_research.contracts.requirement_attribution import attribute_requirements
from deepscout_research.contracts.source_authority import classify_source_authority
from deepscout_research.contracts.source_portfolio import source_portfolio_is_adequate
from deepscout_research.contracts.temporal_claims import TemporalClaim, TemporalRelation

_UNRESOLVED = {
    RequirementCoverageStatus.NOT_RESEARCHED,
    RequirementCoverageStatus.SEARCHED,
    RequirementCoverageStatus.SEARCHED_NO_EVIDENCE,
    RequirementCoverageStatus.EVIDENCE_FOUND,
    RequirementCoverageStatus.PARTIAL,
    RequirementCoverageStatus.CONFLICTING,
    RequirementCoverageStatus.UNSUPPORTED,
}
_STOPWORDS = {
    "about", "after", "also", "and", "come", "con", "della", "delle", "degli",
    "dello", "from", "into", "nella", "nelle", "per", "quali", "that", "the",
    "their", "these", "those", "what", "when", "which", "with",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text.casefold())
        if token not in _STOPWORDS
    }


def _query_matches_requirement(query: str, requirement_text: str) -> bool:
    query_tokens = _tokens(query)
    requirement_tokens = _tokens(requirement_text)
    if not query_tokens or not requirement_tokens:
        return False
    overlap = len(query_tokens & requirement_tokens)
    return overlap >= 2 and overlap / min(len(query_tokens), len(requirement_tokens)) >= 0.15


def _budget_exhausted(row: Any) -> bool:
    if row is None:
        return False
    budget = ResearchBudget(
        max_iterations=row.max_iterations,
        max_wall_time_seconds=row.max_wall_time_seconds,
        max_total_tokens=row.max_total_tokens,
        max_cost_usd=row.max_cost_usd,
        max_sources=row.max_sources,
        max_tool_calls=row.max_tool_calls,
    )
    consumption = BudgetConsumption(
        iterations=row.consumed_iterations,
        wall_time_seconds=row.consumed_wall_time_seconds,
        total_tokens=row.consumed_total_tokens,
        cost_usd=row.consumed_cost_usd,
        sources=row.consumed_sources,
        tool_calls=row.consumed_tool_calls,
    )
    return consumption.is_exhausted(budget)


def _temporal_claims_from_snapshot(store: ResearchStore, run_id: uuid.UUID) -> list[TemporalClaim]:
    row = store.get_run_row(run_id)
    raw = ((row.config_snapshot if row else None) or {}).get("temporal_claims") or []
    claims: list[TemporalClaim] = []
    for item in raw:
        try:
            claim = TemporalClaim.model_validate(item)
            if claim.verified:
                claims.append(claim)
        except Exception:
            continue
    return claims


def _year_from_date(date_text: str) -> int | None:
    match = re.search(r"(20\d{2})", date_text)
    return int(match.group(1)) if match else None


def _temporal_supports_requirement(claims: list[TemporalClaim], requirement_id: str) -> bool:
    if requirement_id in {"R_reg_now", "R_reg_current"}:
        return any(
            claim.temporal_relation
            in {
                TemporalRelation.APPLIES_FROM,
                TemporalRelation.ENTERED_INTO_FORCE,
                TemporalRelation.ENFORCEABLE_FROM,
            }
            and (_year_from_date(claim.date_text) or 0) <= 2026
            for claim in claims
        )
    if requirement_id == "R_reg_later":
        return any(
            claim.temporal_relation
            in {
                TemporalRelation.TRANSITION_UNTIL,
                TemporalRelation.MUST_COMPLY_BY,
                TemporalRelation.SUPERSEDED_FROM,
            }
            or (_year_from_date(claim.date_text) or 0) >= 2027
            for claim in claims
        )
    if requirement_id == "R_reg_apply":
        return _temporal_supports_requirement(claims, "R_reg_now") and _temporal_supports_requirement(
            claims, "R_reg_later"
        )
    if requirement_id in {"R_reg_time", "R_timeline"}:
        return any(
            claim.temporal_relation == TemporalRelation.ENFORCEABLE_FROM for claim in claims
        )
    return False


def _verified_entity_for_president(store: ResearchStore, run_id: uuid.UUID) -> bool:
    row = store.get_run_row(run_id)
    snapshot = row.config_snapshot if row else None
    return bool(((snapshot or {}).get("verified_entities") or {}).get("entity-office-holder"))


def _metadata_enum_values(metadata: dict | None, key: str, enum_type: type) -> set:
    if not isinstance(metadata, dict):
        return set()
    raw = metadata.get(key)
    values = raw if isinstance(raw, list) else [raw]
    parsed = set()
    for value in values:
        try:
            if value:
                parsed.add(enum_type(str(value)))
        except ValueError:
            continue
    return parsed


def _comparison_complete(requirement, claims_text: str) -> bool:
    subjects = requirement.comparison_subjects
    if len(subjects) < 2:
        return bool(
            re.search(
                r"\bvs\b|\bversus\b|compared|comparison|confront|relative to|whereas|while",
                claims_text.casefold(),
            )
        )
    claim_tokens = _tokens(claims_text)

    subject_token_sets = [_tokens(subject) for subject in subjects[:2]]
    common = subject_token_sets[0] & subject_token_sets[1]

    def subject_present(subject: str) -> bool:
        subject_tokens = _tokens(subject) - common
        if subject_tokens & claim_tokens:
            return True
        compact = re.sub(r"[^A-Za-z0-9]", "", subject)
        if not (2 <= len(compact) <= 8 and compact.isupper()):
            return False
        words = re.findall(r"[a-z]+", claims_text.casefold())
        for start in range(len(words)):
            initials = "".join(word[0] for word in words[start : start + len(compact)])
            if len(initials) >= 2 and compact.casefold().startswith(initials[:2]):
                return True
        return False

    return all(subject_present(subject) for subject in subjects[:2])


def _requirement_queries(requirement, candidates, trace: list[dict], executions) -> list[str]:
    queries = {
        candidate.query
        for candidate in candidates
        if _query_matches_requirement(candidate.query, requirement.text)
    }
    for item in trace:
        if item.get("requirement_id") == requirement.requirement_id and item.get("query"):
            queries.add(str(item["query"]))
    for execution in executions:
        if execution.tool_name == "web_search" and _query_matches_requirement(
            execution.input_summary,
            requirement.text,
        ):
            queries.add(execution.input_summary)
    return sorted(queries)


def _gap_cause_without_support(
    *,
    searched_queries: list[str],
    candidate_count: int,
    search_failed: bool,
    source_count: int,
    snapshot_count: int,
    evidence_count: int,
    budget_exhausted: bool,
) -> CoverageGapCause:
    if not searched_queries:
        return (
            CoverageGapCause.BUDGET_EXHAUSTED
            if budget_exhausted
            else CoverageGapCause.NOT_SEARCHED
        )
    if search_failed:
        return CoverageGapCause.SEARCH_EXECUTION_FAILED
    if candidate_count == 0:
        return CoverageGapCause.SEARCH_NO_RESULTS
    if source_count == 0:
        return CoverageGapCause.SOURCE_ADMISSION_FAILED
    if snapshot_count == 0:
        return CoverageGapCause.SOURCE_FETCH_FAILED
    if evidence_count == 0:
        return CoverageGapCause.EXTRACTION_FAILED
    return CoverageGapCause.ATTRIBUTION_FAILED


def evaluate_coverage(
    store: ResearchStore,
    run_id: uuid.UUID,
    contract: ResearchContract,
) -> CoverageMap:
    """Evaluate requirements against only attributable searches and evidence.

    A missing item means this run did not retrieve admissible support. It does not assert that
    evidence does not exist in the world.
    """

    row = store.get_run_row(run_id)
    candidates = store.list_search_candidates(run_id)
    sources = store.list_sources(run_id)
    snapshots = store.list_snapshots_for_run(run_id)
    claims = store.list_claims(run_id)
    evidence = store.list_evidence(run_id)
    executions = store.list_tool_executions(run_id)
    snapshot_by_id = {item.id: item for item in snapshots}
    source_by_id = {item.id: item for item in sources}
    evidence_by_claim = {item.claim_id: item for item in evidence}
    candidate_urls_by_query: dict[str, set[str]] = defaultdict(set)
    for candidate in candidates:
        candidate_urls_by_query[candidate.query].add(candidate.url)

    snapshot = row.config_snapshot if row else None
    trace = list((snapshot or {}).get("coverage_query_trace") or [])
    attempts = list((snapshot or {}).get("coverage_gap_attempts") or [])
    attempted_by_requirement: dict[str, int] = defaultdict(int)
    for attempt in attempts:
        req_id = str(attempt.get("requirement_id") or "")
        if req_id:
            attempted_by_requirement[req_id] += 1

    verified = {
        ClaimVerificationStatus.VERIFIED,
        ClaimVerificationStatus.PARTIALLY_VERIFIED,
    }
    attributed_by_requirement: dict[str, list] = defaultdict(list)
    for claim in claims:
        ev = evidence_by_claim.get(claim.id)
        if ev is None or claim.verification_status not in verified:
            continue
        metadata = ev.extraction_metadata if isinstance(ev.extraction_metadata, dict) else {}
        raw_ids = metadata.get("requirement_ids")
        req_ids = [str(item) for item in raw_ids] if isinstance(raw_ids, list) else []
        if not req_ids:
            req_ids = attribute_requirements(statement=claim.statement, quote=ev.quote, contract=contract)
        for req_id in req_ids:
            attributed_by_requirement[req_id].append(claim)

    temporal_claims = _temporal_claims_from_snapshot(store, run_id)
    has_verified_president = _verified_entity_for_president(store, run_id)
    exhausted = _budget_exhausted(row)
    entries: list[CoverageMapEntry] = []

    for requirement in contract.requirements:
        if requirement.kind == RequirementKind.OUTPUT_FORMAT:
            entries.append(
                CoverageMapEntry(
                    requirement_id=requirement.requirement_id,
                    status=RequirementCoverageStatus.NOT_APPLICABLE,
                    note="Validated against the rendered report, not research evidence.",
                )
            )
            continue

        searched_queries = _requirement_queries(requirement, candidates, trace, executions)
        matching_executions = [
            execution
            for execution in executions
            if execution.tool_name == "web_search"
            and execution.input_summary in searched_queries
        ]
        search_failed = bool(matching_executions) and all(
            execution.status.value == "failed" for execution in matching_executions
        )
        candidate_urls: set[str] = set()
        for query in searched_queries:
            candidate_urls.update(candidate_urls_by_query[query])
        relevant_sources = [source for source in sources if source.canonical_url in candidate_urls]
        relevant_source_ids = {source.id for source in relevant_sources}
        relevant_snapshots = [item for item in snapshots if item.source_id in relevant_source_ids]
        relevant_snapshot_ids = {item.id for item in relevant_snapshots}
        relevant_evidence = [item for item in evidence if item.snapshot_id in relevant_snapshot_ids]
        supporting_claims = list(attributed_by_requirement.get(requirement.requirement_id, []))

        if requirement.requirement_id == "R_president" and has_verified_president:
            status = RequirementCoverageStatus.SUPPORTED
            note = "Verified office-holder entity in structured state."
        elif _temporal_supports_requirement(temporal_claims, requirement.requirement_id):
            status = RequirementCoverageStatus.SUPPORTED
            note = "Verified temporal claim in structured state."
        elif requirement.kind == RequirementKind.SOURCE_POLICY:
            policy_classes = {
                classify_source_authority(url=source.canonical_url, title=source.title).source_class
                for source in sources
            }
            if source_portfolio_is_adequate(requirement, contract, policy_classes):
                status = RequirementCoverageStatus.SUPPORTED
                note = "The run contains a source class required by the source policy."
            else:
                status = RequirementCoverageStatus.PARTIAL if sources else RequirementCoverageStatus.UNSUPPORTED
                note = "The retrieved source portfolio does not satisfy the requested source policy."
        elif supporting_claims:
            status = RequirementCoverageStatus.SUPPORTED
            note = "Verified evidence was attributed to this requirement."
        elif searched_queries:
            status = RequirementCoverageStatus.SEARCHED_NO_EVIDENCE
            note = "The run searched this requirement but did not retrieve attributable evidence."
        else:
            status = RequirementCoverageStatus.NOT_RESEARCHED
            note = "No requirement-scoped search was recorded."

        supporting_ids = [str(claim.id) for claim in supporting_claims]
        source_classes: set[SourceClass] = set()
        evidence_types: set[EvidenceType] = set()
        supporting_text: list[str] = []
        has_numeric = False
        for claim in supporting_claims:
            ev = evidence_by_claim.get(claim.id)
            if ev is None:
                continue
            supporting_text.extend((claim.statement, ev.quote))
            has_numeric = has_numeric or bool(re.search(r"\d", f"{claim.statement} {ev.quote}"))
            source_classes |= _metadata_enum_values(ev.extraction_metadata, "source_class", SourceClass)
            evidence_types |= _metadata_enum_values(ev.extraction_metadata, "evidence_type", EvidenceType)
            snap = snapshot_by_id.get(ev.snapshot_id)
            source = source_by_id.get(snap.source_id) if snap else None
            if source:
                source_classes.add(
                    classify_source_authority(
                        url=source.canonical_url,
                        title=source.title,
                    ).source_class
                )

        gap_cause: CoverageGapCause | None = None
        if status == RequirementCoverageStatus.SUPPORTED and requirement.quantification_required and not has_numeric:
            status = RequirementCoverageStatus.PARTIAL
            gap_cause = CoverageGapCause.NUMERIC_EVIDENCE_MISSING
            note = "Qualitative support was found, but no attributable numeric evidence was found."
        if status == RequirementCoverageStatus.SUPPORTED and requirement.kind == RequirementKind.COMPARISON:
            if not _comparison_complete(requirement, " ".join(supporting_text)):
                status = RequirementCoverageStatus.PARTIAL
                gap_cause = CoverageGapCause.COMPARISON_INCOMPLETE
                note = "Evidence does not cover both sides of the requested comparison."
        if status == RequirementCoverageStatus.SUPPORTED and requirement.kind == RequirementKind.TIMELINE:
            required_times = set(re.findall(r"\b\d+", requirement.text))
            supported_times = set(re.findall(r"\b\d+", " ".join(supporting_text)))
            if required_times and not required_times <= supported_times:
                status = RequirementCoverageStatus.PARTIAL
                gap_cause = CoverageGapCause.TIMELINE_INCOMPLETE
                note = "Evidence does not cover every requested timeframe."
        if status == RequirementCoverageStatus.SUPPORTED and requirement.required_evidence_types:
            if not set(requirement.required_evidence_types) & evidence_types:
                status = RequirementCoverageStatus.PARTIAL
                gap_cause = CoverageGapCause.SOURCE_PORTFOLIO_INADEQUATE
                note = "Attributable evidence lacks the requested evidence type."
        if status == RequirementCoverageStatus.SUPPORTED and not source_portfolio_is_adequate(
            requirement, contract, source_classes
        ):
            status = RequirementCoverageStatus.PARTIAL
            gap_cause = CoverageGapCause.SOURCE_PORTFOLIO_INADEQUATE
            note = "Attributable evidence lacks an adequate source class for this requirement."
        if status in _UNRESOLVED and gap_cause is None:
            gap_cause = _gap_cause_without_support(
                searched_queries=searched_queries,
                candidate_count=len(candidate_urls),
                search_failed=search_failed,
                source_count=len(relevant_sources),
                snapshot_count=len(relevant_snapshots),
                evidence_count=len(relevant_evidence),
                budget_exhausted=exhausted,
            )

        entries.append(
            CoverageMapEntry(
                requirement_id=requirement.requirement_id,
                status=status,
                note=note,
                supporting_claim_ids=supporting_ids[:20],
                gap_cause=gap_cause,
                searched_queries=searched_queries[:12],
                candidate_source_count=len(candidate_urls),
                admissible_source_count=len(relevant_snapshots),
                corrective_attempts=attempted_by_requirement[requirement.requirement_id],
                source_classes=sorted(source_classes, key=lambda item: item.value)[:10],
                evidence_types=sorted(evidence_types, key=lambda item: item.value)[:10],
            )
        )

    by_id = {entry.requirement_id: entry for entry in entries}
    for requirement in contract.requirements:
        if not requirement.depends_on or requirement.requirement_id not in by_id:
            continue
        unresolved = [
            dep
            for dep in requirement.depends_on
            if dep in by_id and by_id[dep].status != RequirementCoverageStatus.SUPPORTED
        ]
        if unresolved:
            entry = by_id[requirement.requirement_id]
            entry.status = RequirementCoverageStatus.UNSUPPORTED
            entry.note = f"Blocked by unresolved prerequisite(s): {', '.join(unresolved)}."
            entry.gap_cause = CoverageGapCause.EVIDENCE_NOT_RETRIEVED

    primary = by_id.get("R0")
    substantive = [
        entry
        for entry in entries
        if entry.requirement_id != "R0"
        and entry.status != RequirementCoverageStatus.NOT_APPLICABLE
        and next(
            (
                req.materiality == "central"
                for req in contract.requirements
                if req.requirement_id == entry.requirement_id
            ),
            False,
        )
    ]
    if primary and substantive:
        if all(entry.status == RequirementCoverageStatus.SUPPORTED for entry in substantive):
            primary.status = RequirementCoverageStatus.SUPPORTED
            primary.gap_cause = None
            primary.note = "All central material requirements are supported."
        else:
            primary.status = RequirementCoverageStatus.PARTIAL
            primary.gap_cause = CoverageGapCause.EVIDENCE_NOT_RETRIEVED
            primary.note = "The primary objective remains partial because material requirements are unresolved."

    requirements_by_id = {item.requirement_id: item for item in contract.requirements}
    critical_unresolved = [
        entry.requirement_id
        for entry in entries
        if entry.status in _UNRESOLVED and requirements_by_id[entry.requirement_id].critical
    ]
    material_gaps = [
        entry.requirement_id
        for entry in entries
        if entry.status in _UNRESOLVED
        and requirements_by_id[entry.requirement_id].materiality == "central"
    ]
    return CoverageMap(
        entries=entries,
        critical_unresolved=critical_unresolved[:15],
        material_gaps=material_gaps[:15],
    )


def gap_search_queries(contract: ResearchContract, coverage: CoverageMap, *, limit: int = 3) -> list[str]:
    from deepscout_research.contracts.query_planning import gap_queries_for_requirement

    queries: list[str] = []
    gap_ids = set(coverage.material_gaps)
    for requirement in contract.requirements:
        if requirement.requirement_id not in gap_ids or requirement.kind == RequirementKind.OUTPUT_FORMAT:
            continue
        queries.extend(gap_queries_for_requirement(requirement, contract, round_number=1))
        if len(queries) >= limit:
            break
    return queries[:limit]
