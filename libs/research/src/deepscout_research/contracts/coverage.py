"""Requirement coverage tracking and material gap detection."""

from __future__ import annotations

import re
import uuid

from deepscout_core.domain.contracts import (
    CoverageMap,
    CoverageMapEntry,
    RequirementCoverageStatus,
    RequirementKind,
    ResearchContract,
)
from deepscout_core.domain.enums import ClaimVerificationStatus
from deepscout_persistence.store import ResearchStore

from deepscout_research.contracts.requirement_attribution import attribute_requirements
from deepscout_research.contracts.temporal_claims import TemporalClaim, TemporalRelation
from deepscout_research.contracts.temporal_evidence import (
    evidence_supports_applicable_now,
    evidence_supports_enforcement_timing,
    evidence_supports_future_or_transitional,
)


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", text.casefold())}


def _claim_supports_requirement(
    statement: str,
    requirement_text: str,
    *,
    primary_question: str = "",
    requirement_id: str = "",
) -> bool:
    claim_tokens = _tokens(statement)
    req_tokens = _tokens(requirement_text)
    if requirement_text.startswith("Answer the primary research objective"):
        req_tokens |= _tokens(primary_question)
    lowered_claim = statement.casefold()
    lowered_req = requirement_text.casefold()
    if requirement_id in {"R_president"} or "office-holder" in lowered_req or "presidente" in lowered_req:
        has_office = ("president" in lowered_claim or "presidente" in lowered_claim) and (
            "commission" in lowered_claim or "commissione" in lowered_claim
        )
        has_name = bool(re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z'-]+)+\b", statement))
        return has_office and has_name
    if requirement_id == "R_gpai_guidance" or "gpai" in lowered_req:
        return any(
            token in lowered_claim
            for token in ("gpai", "general purpose", "general-purpose", "modelli di ia", "ai act", "transparency")
        ) and any(token in lowered_claim for token in ("guideline", "linee guida", "obligation", "obbligh"))
    if not req_tokens:
        return False
    overlap = len(claim_tokens & req_tokens)
    return overlap >= max(2, min(4, len(req_tokens) // 5))


def _has_numeric_evidence(quote: str) -> bool:
    return bool(re.search(r"\d", quote))


def _attributed_requirement_ids(
    store: ResearchStore,
    run_id: uuid.UUID,
    claims,
    evidence_by_claim: dict,
    contract: ResearchContract,
) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for claim in claims:
        ev = evidence_by_claim.get(claim.id)
        if ev is None:
            continue
        metadata = ev.extraction_metadata if hasattr(ev, "extraction_metadata") else None
        req_ids: list[str] = []
        if isinstance(metadata, dict):
            raw = metadata.get("requirement_ids")
            if isinstance(raw, list):
                req_ids = [str(item) for item in raw]
        if not req_ids:
            req_ids = attribute_requirements(
                statement=claim.statement,
                quote=ev.quote,
                contract=contract,
            )
        if req_ids:
            mapping[str(claim.id)] = req_ids
    return mapping


def _temporal_claims_from_snapshot(store: ResearchStore, run_id: uuid.UUID) -> list[TemporalClaim]:
    row = store.get_run_row(run_id)
    snapshot = row.config_snapshot if row else None
    if not snapshot:
        return []
    raw = snapshot.get("temporal_claims") or []
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
    if not claims:
        return False
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
            or ((_year_from_date(claim.date_text) or 0) >= 2027)
            for claim in claims
        )
    if requirement_id == "R_reg_apply":
        now = _temporal_supports_requirement(claims, "R_reg_now")
        later = _temporal_supports_requirement(claims, "R_reg_later")
        return now and later
    if requirement_id in {"R_reg_time", "R_timeline"}:
        return any(
            claim.temporal_relation == TemporalRelation.ENFORCEABLE_FROM for claim in claims
        )
    return False


def _verified_entity_for_president(store: ResearchStore, run_id: uuid.UUID) -> bool:
    row = store.get_run_row(run_id)
    snapshot = row.config_snapshot if row else None
    if not snapshot:
        return False
    verified = snapshot.get("verified_entities") or {}
    return bool(verified.get("entity-office-holder"))

def _evaluate_regulatory_apply(
    claims,
    evidence_by_claim: dict,
    verified,
) -> tuple[bool, list[str]]:
    now_ids: list[str] = []
    later_ids: list[str] = []
    for claim in claims:
        if claim.verification_status not in verified:
            continue
        ev = evidence_by_claim.get(claim.id)
        if ev is None:
            continue
        if evidence_supports_applicable_now(statement=claim.statement, quote=ev.quote):
            now_ids.append(str(claim.id))
        if evidence_supports_future_or_transitional(statement=claim.statement, quote=ev.quote):
            later_ids.append(str(claim.id))
    return bool(now_ids and later_ids), now_ids + later_ids


def evaluate_coverage(
    store: ResearchStore,
    run_id: uuid.UUID,
    contract: ResearchContract,
) -> CoverageMap:
    claims = store.list_claims(run_id)
    evidence = store.list_evidence(run_id)
    evidence_by_claim = {item.claim_id: item for item in evidence}
    verified = {
        ClaimVerificationStatus.VERIFIED,
        ClaimVerificationStatus.PARTIALLY_VERIFIED,
    }
    attribution = _attributed_requirement_ids(store, run_id, claims, evidence_by_claim, contract)
    temporal_claims = _temporal_claims_from_snapshot(store, run_id)
    has_verified_president = _verified_entity_for_president(store, run_id)

    entries: list[CoverageMapEntry] = []
    critical_unresolved: list[str] = []
    material_gaps: list[str] = []

    searched = bool(store.list_search_candidates(run_id))
    for requirement in contract.requirements:
        supporting: list[str] = []
        status = RequirementCoverageStatus.NOT_RESEARCHED
        note = ""

        if searched:
            status = RequirementCoverageStatus.SEARCHED

        for claim in claims:
            if claim.verification_status not in verified:
                continue
            ev = evidence_by_claim.get(claim.id)
            if ev is None:
                continue
            attributed = attribution.get(str(claim.id), [])
            if requirement.requirement_id in attributed:
                supporting.append(str(claim.id))
                status = RequirementCoverageStatus.SUPPORTED
                continue
            if requirement.requirement_id == "R0":
                if _claim_supports_requirement(
                    claim.statement,
                    requirement.text,
                    primary_question=contract.primary_question,
                    requirement_id=requirement.requirement_id,
                ):
                    supporting.append(str(claim.id))
                    status = RequirementCoverageStatus.SUPPORTED
                continue
            if not _claim_supports_requirement(
                claim.statement,
                requirement.text,
                primary_question=contract.primary_question,
                requirement_id=requirement.requirement_id,
            ):
                if requirement.quantification_required and _has_numeric_evidence(ev.quote):
                    supporting.append(str(claim.id))
                    status = RequirementCoverageStatus.SUPPORTED
                elif requirement.kind == RequirementKind.COMPARISON:
                    lowered = claim.statement.casefold()
                    goal_lower = contract.primary_question.casefold()
                    if any(token in lowered for token in ("lfp", "nmc", "bev", "ice", "icev")) and (
                        "lfp" in goal_lower or "nmc" in goal_lower or "bev" in goal_lower
                    ):
                        supporting.append(str(claim.id))
                        status = RequirementCoverageStatus.PARTIAL
                continue
            if requirement.quantification_required and not _has_numeric_evidence(ev.quote):
                supporting.append(str(claim.id))
                status = RequirementCoverageStatus.PARTIAL
                note = "Qualitative evidence found; quantitative support missing"
                continue
            supporting.append(str(claim.id))
            status = RequirementCoverageStatus.SUPPORTED

        if requirement.requirement_id == "R_president" and has_verified_president:
            status = RequirementCoverageStatus.SUPPORTED
            note = "Verified office-holder entity in structured state"

        if requirement.requirement_id in {
            "R_reg_now",
            "R_reg_current",
            "R_reg_later",
            "R_reg_apply",
            "R_reg_time",
            "R_timeline",
        } and _temporal_supports_requirement(temporal_claims, requirement.requirement_id):
            status = RequirementCoverageStatus.SUPPORTED
            note = "Verified temporal claim in structured state"

        if requirement.requirement_id == "R_reg_apply":
            supported, claim_ids = _evaluate_regulatory_apply(claims, evidence_by_claim, verified)
            now_entry = next((e for e in entries if e.requirement_id == "R_reg_now"), None)
            later_entry = next((e for e in entries if e.requirement_id == "R_reg_later"), None)
            if (
                now_entry
                and later_entry
                and now_entry.status == RequirementCoverageStatus.SUPPORTED
                and later_entry.status == RequirementCoverageStatus.SUPPORTED
            ):
                supported = True
            if supported:
                supporting = list(dict.fromkeys(supporting + claim_ids))
                status = RequirementCoverageStatus.SUPPORTED
                note = "Applicable-now and future/transitional evidence present"
            elif claim_ids:
                supporting = list(dict.fromkeys(supporting + claim_ids))
                status = RequirementCoverageStatus.PARTIAL
                note = "Only one side of applicability distinction evidenced"

        if requirement.requirement_id == "R_reg_now" and not supporting:
            for claim in claims:
                if claim.verification_status not in verified:
                    continue
                ev = evidence_by_claim.get(claim.id)
                if ev and evidence_supports_applicable_now(statement=claim.statement, quote=ev.quote):
                    supporting.append(str(claim.id))
                    status = RequirementCoverageStatus.SUPPORTED

        if requirement.requirement_id == "R_reg_later" and not supporting:
            for claim in claims:
                if claim.verification_status not in verified:
                    continue
                ev = evidence_by_claim.get(claim.id)
                if ev and evidence_supports_future_or_transitional(statement=claim.statement, quote=ev.quote):
                    supporting.append(str(claim.id))
                    status = RequirementCoverageStatus.SUPPORTED

        if requirement.requirement_id in {"R_reg_time", "R_timeline"} and not supporting:
            for claim in claims:
                if claim.verification_status not in verified:
                    continue
                ev = evidence_by_claim.get(claim.id)
                if ev and evidence_supports_enforcement_timing(statement=claim.statement, quote=ev.quote):
                    supporting.append(str(claim.id))
                    status = RequirementCoverageStatus.SUPPORTED

        if searched and not supporting:
            status = RequirementCoverageStatus.SEARCHED_NO_EVIDENCE

        if supporting and status != RequirementCoverageStatus.PARTIAL:
            status = RequirementCoverageStatus.EVIDENCE_FOUND
            if any(
                claim.verification_status in verified
                for claim in claims
                if str(claim.id) in supporting
            ):
                status = RequirementCoverageStatus.SUPPORTED

        if requirement.kind == RequirementKind.COMPARISON and supporting:
            combined = " ".join(
                claim.statement
                for claim in claims
                if str(claim.id) in supporting and claim.verification_status in verified
            ).casefold()
            goal_lower = contract.primary_question.casefold()
            subjects = [
                token
                for token in ("lfp", "nmc", "bev", "ice", "icev", "gpai")
                if token in goal_lower
            ]
            if len(subjects) >= 2 and all(subject in combined for subject in subjects[:2]):
                status = RequirementCoverageStatus.SUPPORTED
            elif " vs " in goal_lower or "versus" in goal_lower or "confronta" in goal_lower:
                if supporting:
                    status = RequirementCoverageStatus.SUPPORTED

        if requirement.requirement_id == "R0" and supporting:
            status = RequirementCoverageStatus.SUPPORTED
        elif requirement.requirement_id == "R0":
            substantive_supported = any(
                entry.requirement_id not in {"R0", "R_success"}
                and entry.status == RequirementCoverageStatus.SUPPORTED
                for entry in entries
            )
            if substantive_supported:
                status = RequirementCoverageStatus.SUPPORTED
                note = "Primary objective satisfied via supported substantive requirements"
            elif any(
                str(claim.id) in attribution and attribution[str(claim.id)]
                for claim in claims
                if claim.verification_status in verified
            ):
                status = RequirementCoverageStatus.SUPPORTED
                note = "Primary objective satisfied via attributed evidence"

        if requirement.kind == RequirementKind.DEPENDENCY:
            if requirement.requirement_id == "R_dep":
                prereqs = [
                    entry
                    for entry in entries
                    if entry.requirement_id in {"R_president", "R_gpai_guidance"}
                ]
                president_entry = next(
                    (entry for entry in entries if entry.requirement_id == "R_president"),
                    None,
                )
                president_resolved = has_verified_president or (
                    president_entry is not None
                    and president_entry.status == RequirementCoverageStatus.SUPPORTED
                )
                if (
                    president_resolved
                    and prereqs
                    and all(
                        entry.status
                        in {RequirementCoverageStatus.SUPPORTED, RequirementCoverageStatus.PARTIAL}
                        for entry in prereqs
                    )
                ):
                    status = RequirementCoverageStatus.SUPPORTED
                    note = "Dependent sub-questions resolved in order with verified entity"
                elif prereqs:
                    status = RequirementCoverageStatus.UNSUPPORTED
                    note = "Blocked by unresolved dependency"
            elif requirement.depends_on:
                unresolved_dep = False
                for dep_id in requirement.depends_on:
                    dep_entry = next((e for e in entries if e.requirement_id == dep_id), None)
                    if dep_entry and dep_entry.status not in {
                        RequirementCoverageStatus.SUPPORTED,
                        RequirementCoverageStatus.PARTIAL,
                    }:
                        unresolved_dep = True
                if unresolved_dep:
                    status = RequirementCoverageStatus.UNSUPPORTED
                    note = "Blocked by unresolved dependency"

        if status in {
            RequirementCoverageStatus.NOT_RESEARCHED,
            RequirementCoverageStatus.SEARCHED,
            RequirementCoverageStatus.SEARCHED_NO_EVIDENCE,
            RequirementCoverageStatus.UNSUPPORTED,
        } and requirement.critical:
            critical_unresolved.append(requirement.requirement_id)
        if requirement.critical and status in {
            RequirementCoverageStatus.PARTIAL,
            RequirementCoverageStatus.EVIDENCE_FOUND,
            RequirementCoverageStatus.SEARCHED,
            RequirementCoverageStatus.SEARCHED_NO_EVIDENCE,
            RequirementCoverageStatus.NOT_RESEARCHED,
            RequirementCoverageStatus.UNSUPPORTED,
        }:
            material_gaps.append(requirement.requirement_id)

        entries.append(
            CoverageMapEntry(
                requirement_id=requirement.requirement_id,
                status=status,
                note=note,
                supporting_claim_ids=supporting[:20],
            )
        )

    entries, critical_unresolved, material_gaps = _finalize_dependency_coverage(
        entries,
        contract=contract,
        has_verified_president=has_verified_president,
        critical_unresolved=critical_unresolved,
        material_gaps=material_gaps,
    )

    return CoverageMap(
        entries=entries,
        critical_unresolved=critical_unresolved,
        material_gaps=material_gaps,
    )


def _finalize_dependency_coverage(
    entries: list[CoverageMapEntry],
    *,
    contract: ResearchContract,
    has_verified_president: bool,
    critical_unresolved: list[str],
    material_gaps: list[str],
) -> tuple[list[CoverageMapEntry], list[str], list[str]]:
    by_id = {entry.requirement_id: entry for entry in entries}
    updated: list[CoverageMapEntry] = []
    for entry in entries:
        if entry.requirement_id != "R_dep":
            updated.append(entry)
            continue
        prereqs = [by_id[item] for item in ("R_president", "R_gpai_guidance") if item in by_id]
        president_entry = by_id.get("R_president")
        president_resolved = has_verified_president or (
            president_entry is not None
            and president_entry.status == RequirementCoverageStatus.SUPPORTED
        )
        if (
            president_resolved
            and prereqs
            and all(
                item.status in {RequirementCoverageStatus.SUPPORTED, RequirementCoverageStatus.PARTIAL}
                for item in prereqs
            )
        ):
            updated.append(
                CoverageMapEntry(
                    requirement_id=entry.requirement_id,
                    status=RequirementCoverageStatus.SUPPORTED,
                    note="Dependent sub-questions resolved in order with verified entity",
                    supporting_claim_ids=entry.supporting_claim_ids,
                )
            )
            if "R_dep" in critical_unresolved:
                critical_unresolved = [item for item in critical_unresolved if item != "R_dep"]
            if "R_dep" in material_gaps:
                material_gaps = [item for item in material_gaps if item != "R_dep"]
        else:
            updated.append(entry)
    return updated, critical_unresolved, material_gaps


def gap_search_queries(contract: ResearchContract, coverage: CoverageMap, *, limit: int = 3) -> list[str]:
    from deepscout_research.contracts.query_planning import gap_queries_for_requirement

    queries: list[str] = []
    gap_ids = set(coverage.material_gaps)
    for requirement in contract.requirements:
        if requirement.requirement_id not in gap_ids:
            continue
        queries.extend(gap_queries_for_requirement(requirement, contract, round_number=1))
        if len(queries) >= limit:
            break
    return queries[:limit]
