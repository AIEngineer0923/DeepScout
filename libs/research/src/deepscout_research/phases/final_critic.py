"""Final answer critic — evaluates report against original user request."""

from __future__ import annotations

import re
import uuid

from deepscout_core.domain.contracts import (
    CoverageMap,
    FinalCriticResult,
    FinalCriticVerdict,
    ReportContract,
    RequirementCoverageStatus,
    ResearchContract,
)
from deepscout_persistence.store import ResearchStore

from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.evidence_relevance import claim_specificity_allowed
from deepscout_research.contracts.extract import (
    contract_from_snapshot,
    report_contract_from_snapshot,
)
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

    if contract is not None:
        cov = coverage or evaluate_coverage(store, run_id, contract)
        for entry in cov.entries:
            req = next(
                (item for item in contract.requirements if item.requirement_id == entry.requirement_id),
                None,
            )
            if req is None or not req.critical:
                continue
            if req.requirement_id == "R0":
                substantive = [
                    entry
                    for entry in cov.entries
                    if entry.requirement_id not in {"R0", "R_success"}
                    and entry.status == RequirementCoverageStatus.SUPPORTED
                ]
                if substantive:
                    continue
            if entry.status in {
                RequirementCoverageStatus.NOT_RESEARCHED,
                RequirementCoverageStatus.SEARCHED,
                RequirementCoverageStatus.SEARCHED_NO_EVIDENCE,
                RequirementCoverageStatus.UNSUPPORTED,
            }:
                unresolved.append(req.requirement_id)
                issues.append(f"Critical requirement unresolved: {req.text[:120]}")
                reason_codes.append("MISSING_REQUIREMENT")
            elif entry.status == RequirementCoverageStatus.PARTIAL and req.quantification_required:
                unresolved.append(req.requirement_id)
                issues.append(f"Quantitative requirement only partially supported: {req.text[:120]}")
                reason_codes.append("UNSUPPORTED_NUMERIC_CLAIM")

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

    reason_codes = list(dict.fromkeys(reason_codes))
    if issues and unresolved:
        return FinalCriticResult(
            verdict=FinalCriticVerdict.BLOCKED_BY_EVIDENCE,
            issues=issues[:20],
            reason_codes=reason_codes[:20],
            unresolved_requirements=unresolved[:15],
            revision_notes="Publish partial answer with explicit unresolved requirements",
        )
    if unresolved:
        return FinalCriticResult(
            verdict=FinalCriticVerdict.RESEARCH_GAP,
            issues=issues[:20],
            reason_codes=reason_codes[:20],
            unresolved_requirements=unresolved[:15],
            revision_notes="Material research gaps remain after bounded attempts",
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
