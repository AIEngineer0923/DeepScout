"""Final answer critic — evaluates report against original user request."""

from __future__ import annotations

import re
import uuid

from deepscout_core.domain.contracts import (
    CoverageGapCause,
    CoverageMap,
    FinalCriticResult,
    FinalCriticVerdict,
    ReportContract,
    RequirementCoverageStatus,
    ResearchContract,
)
from deepscout_core.domain.research_profiles import research_profile
from deepscout_persistence.store import ResearchStore

from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.deliverables import validate_report_deliverable
from deepscout_research.contracts.evidence_relevance import claim_specificity_allowed
from deepscout_research.contracts.extract import (
    contract_from_snapshot,
    report_contract_from_snapshot,
)
from deepscout_research.contracts.numeric_constraints import markdown_allocation_errors
from deepscout_research.contracts.source_authority import (
    is_source_admissible,
    violates_only_constraint,
)

_TASK_LEAK_PATTERNS = (
    re.compile(r"^\s*[-*]?\s*\([^)]*\)\s*(collect|gather|search|analyze|synthesize)\b", re.I),
    re.compile(r"^##\s*Questions\b", re.I),
    re.compile(r"\banswer provided\b", re.I),
    re.compile(r"\bMarkdown final research report\b", re.I),
)
_BIBLIOGRAPHY_HEADING = re.compile(r"(?im)^#{1,6}\s+(?:Sources\s+Cited|Fonti\s+citate)\s*$")
_ACTIONABLE_GAPS = {
    CoverageGapCause.NOT_SEARCHED,
    CoverageGapCause.SEARCH_EXECUTION_FAILED,
    CoverageGapCause.SEARCH_NO_RESULTS,
    CoverageGapCause.SOURCE_FETCH_FAILED,
    CoverageGapCause.SOURCE_ADMISSION_FAILED,
    CoverageGapCause.EXTRACTION_FAILED,
    CoverageGapCause.ATTRIBUTION_FAILED,
    CoverageGapCause.NUMERIC_EVIDENCE_MISSING,
    CoverageGapCause.COMPARISON_INCOMPLETE,
    CoverageGapCause.TIMELINE_INCOMPLETE,
    CoverageGapCause.SOURCE_PORTFOLIO_INADEQUATE,
    CoverageGapCause.EVIDENCE_NOT_RETRIEVED,
}


def _report_text(store: ResearchStore, run_id: uuid.UUID) -> str:
    report = store.get_report(run_id)
    if report is None:
        return ""
    return report.body_markdown or ""


def run_final_answer_critic(
    store: ResearchStore,
    run_id: uuid.UUID,
    *,
    research_contract: ResearchContract | None = None,
    report_contract: ReportContract | None = None,
    coverage: CoverageMap | None = None,
) -> FinalCriticResult:
    row = store.get_run_row(run_id)
    snapshot = row.config_snapshot if row else None
    contract = research_contract or contract_from_snapshot(snapshot)
    report_spec = report_contract or report_contract_from_snapshot(snapshot)
    body = _report_text(store, run_id)
    issues: list[str] = []
    reason_codes: list[str] = []
    unresolved: list[str] = []
    deliverable_valid = True

    if not body.strip():
        return FinalCriticResult(
            verdict=FinalCriticVerdict.REVISION_REQUIRED,
            issues=["Report body is empty"],
            reason_codes=["REPORT_EMPTY"],
            revision_notes="Generate report content before publication",
        )

    for pattern in _TASK_LEAK_PATTERNS:
        if pattern.search(body):
            issues.append("Report contains internal planner or debug scaffolding")
            reason_codes.append("INTERNAL_TASK_LEAK")

    if len(_BIBLIOGRAPHY_HEADING.findall(body)) != 1:
        issues.append("Report must contain exactly one localized bibliography")
        reason_codes.append("DUPLICATE_OR_MISSING_BIBLIOGRAPHY")

    if contract is not None:
        for conflict in contract.constraint_conflicts:
            values = re.findall(r"\d+(?:[.,]\d+)?", conflict)
            conflict_disclosed = bool(
                re.search(r"conflict|contradd|incompatib|ambig", body, re.I)
                and all(value in body for value in values)
            )
            if not conflict_disclosed:
                issues.append(f"Conflicting user constraint was not disclosed: {conflict}")
                reason_codes.append("USER_CONSTRAINT_CONFLICT_HIDDEN")
        arithmetic_errors = markdown_allocation_errors(body)
        if arithmetic_errors:
            issues.append("Allocation table arithmetic does not match its stated total")
            reason_codes.append("ARITHMETIC_CONSTRAINT_MISMATCH")
        deliverable_validation = validate_report_deliverable(body, contract.deliverable)
        deliverable_valid = deliverable_validation.valid
        store.merge_config_snapshot(
            run_id,
            {
                "deliverable_validation": deliverable_validation.model_dump(mode="json"),
            },
        )
        if not deliverable_valid:
            issues.extend(
                f"Requested deliverable constraint failed: {item}"
                for item in deliverable_validation.issues[:10]
            )
            reason_codes.append("DELIVERABLE_CONSTRAINT_MISMATCH")
        cov = coverage or evaluate_coverage(store, run_id, contract)
        for entry in cov.entries:
            req = next(
                (
                    item
                    for item in contract.requirements
                    if item.requirement_id == entry.requirement_id
                ),
                None,
            )
            if req is None or not req.critical:
                continue
            if entry.status in {
                RequirementCoverageStatus.NOT_RESEARCHED,
                RequirementCoverageStatus.SEARCHED,
                RequirementCoverageStatus.SEARCHED_NO_EVIDENCE,
                RequirementCoverageStatus.EVIDENCE_FOUND,
                RequirementCoverageStatus.PARTIAL,
                RequirementCoverageStatus.CONFLICTING,
                RequirementCoverageStatus.UNSUPPORTED,
            }:
                unresolved.append(req.requirement_id)
                if entry.gap_cause == CoverageGapCause.NUMERIC_EVIDENCE_MISSING:
                    issues.append(
                        f"Quantitative requirement only partially supported: {req.text[:120]}"
                    )
                    reason_codes.append("UNSUPPORTED_NUMERIC_CLAIM")
                elif entry.gap_cause == CoverageGapCause.COMPARISON_INCOMPLETE:
                    issues.append(f"Requested comparison is incomplete: {req.text[:120]}")
                    reason_codes.append("INADEQUATE_COMPARISON")
                elif entry.gap_cause == CoverageGapCause.TIMELINE_INCOMPLETE:
                    issues.append(f"Requested timeline is incomplete: {req.text[:120]}")
                    reason_codes.append("INCOMPLETE_TIMELINE")
                elif entry.gap_cause == CoverageGapCause.SOURCE_PORTFOLIO_INADEQUATE:
                    issues.append(f"Source portfolio is inadequate: {req.text[:120]}")
                    reason_codes.append("SOURCE_PORTFOLIO_INADEQUATE")
                else:
                    issues.append(f"Critical requirement unresolved: {req.text[:120]}")
                    reason_codes.append("MISSING_REQUIREMENT")

        prefs = store.list_source_preferences(run_id)
        sources = store.list_sources(run_id)
        for source in sources:
            if violates_only_constraint(source.canonical_url, contract=contract):
                if source.canonical_url in body:
                    issues.append(f"Non-admissible source cited under only-policy: {source.domain}")
                    reason_codes.append("SOURCE_POLICY_VIOLATION")
            admissible, _ = is_source_admissible(
                source.canonical_url,
                contract=contract,
                preferences=prefs,
                title=source.title or "",
            )
            if not admissible and source.canonical_url in body:
                issues.append(f"Inadmissible source appears in report: {source.domain}")
                reason_codes.append("SOURCE_POLICY_VIOLATION")

        claims = store.list_claims(run_id)
        evidence = store.list_evidence(run_id)
        evidence_by_claim = {item.claim_id: item for item in evidence}
        for claim in claims:
            ev = evidence_by_claim.get(claim.id)
            if ev is None:
                continue
            if not claim_specificity_allowed(claim=claim.statement, evidence_quote=ev.quote):
                issues.append("Numerical claim exceeds evidence specificity")
                reason_codes.append("UNSUPPORTED_NUMERIC_CLAIM")

    if "## Sources\n" in body and "## Sources Cited" not in body:
        if body.count("- [") > 25:
            issues.append("Report bibliography may include non-cited consulted sources")

    if report_spec is not None:
        aliases = {
            "Executive Summary": ("Executive Summary", "Sintesi esecutiva"),
            "Analysis": ("Analysis", "Analisi"),
            "Timeline and Applicability": (
                "Timeline and Applicability",
                "Cronologia e applicabilità",
            ),
            "Comparison": ("Comparison", "Confronto"),
            "Quantitative Results": ("Quantitative Results", "Risultati quantitativi"),
            "Limitations and Uncertainty": (
                "Limitations and Uncertainty",
                "Limitazioni e incertezza",
            ),
            "Sources Cited": ("Sources Cited", "Fonti citate"),
        }
        for section in report_spec.sections:
            if not section.required:
                continue
            headings = aliases.get(section.heading, (section.heading,))
            if not any(
                re.search(rf"(?im)^#{{1,6}}\s+{re.escape(item)}\s*$", body) for item in headings
            ):
                issues.append(f"Required report section missing: {section.heading}")
                reason_codes.append("REPORT_SECTION_MISMATCH")

    if re.search(r"(?i)(?:no|insufficient) evidence (?:exists|is available)", body):
        actionable = any(
            entry.requirement_id in unresolved and entry.gap_cause in _ACTIONABLE_GAPS
            for entry in (cov.entries if contract is not None else [])
        )
        if actionable:
            issues.append("Report overstates a retrieval gap as evidence non-existence")
            reason_codes.append("FALSE_INSUFFICIENT_EVIDENCE")

    reason_codes = list(dict.fromkeys(reason_codes))
    unresolved = list(dict.fromkeys(unresolved))
    if contract is not None:
        store.merge_config_snapshot(
            run_id,
            {
                "answer_completeness": {
                    "deliverable_complete": deliverable_valid,
                    "evidence_complete": not unresolved,
                    "unresolved_requirement_ids": unresolved[:15],
                }
            },
        )
    if not deliverable_valid:
        return FinalCriticResult(
            verdict=FinalCriticVerdict.REVISION_REQUIRED,
            issues=issues[:20],
            reason_codes=reason_codes[:20],
            unresolved_requirements=unresolved[:15],
            revision_notes=(
                "Repair the requested deliverable itself: return one complete Markdown table "
                "with the exact requested entity count, category quotas, and allocation total. "
                "Keep sparse-evidence rows but label their confidence/uncertainty explicitly."
            ),
        )
    if unresolved:
        profile = research_profile(row.research_mode if row else None)
        run = store.get_run(run_id)
        budget_available = bool(run and not store.get_consumption(run_id).is_exhausted(run.budget))
        rounds_used = int((snapshot or {}).get("coverage_research_rounds") or 0)
        round_limit = int(
            (snapshot or {}).get("coverage_round_limit") or profile.max_coverage_rounds
        )
        entry_by_id = {entry.requirement_id: entry for entry in cov.entries}
        can_research = (
            budget_available
            and rounds_used < round_limit
            and any(
                entry_by_id[req_id].gap_cause in _ACTIONABLE_GAPS
                and entry_by_id[req_id].gap_cause != CoverageGapCause.BUDGET_EXHAUSTED
                and entry_by_id[req_id].corrective_attempts < profile.max_coverage_rounds
                for req_id in unresolved
                if req_id in entry_by_id
            )
        )
        if can_research:
            return FinalCriticResult(
                verdict=FinalCriticVerdict.RESEARCH_GAP,
                issues=issues[:20],
                reason_codes=reason_codes[:20],
                unresolved_requirements=unresolved[:15],
                revision_notes="Run bounded requirement-specific corrective research before publication",
            )
        return FinalCriticResult(
            verdict=FinalCriticVerdict.BLOCKED_BY_EVIDENCE,
            issues=issues[:20],
            reason_codes=reason_codes[:20],
            unresolved_requirements=unresolved[:15],
            revision_notes="Publish partial answer with explicit unresolved requirements",
        )
    if issues:
        return FinalCriticResult(
            verdict=FinalCriticVerdict.REVISION_REQUIRED,
            issues=issues[:20],
            reason_codes=reason_codes[:20],
            revision_notes="Rewrite report from existing evidence",
        )
    _ = report_spec
    return FinalCriticResult(verdict=FinalCriticVerdict.PASS, issues=[], reason_codes=[])
