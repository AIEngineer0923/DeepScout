"""Map verified claims and evidence to ResearchContract requirement IDs."""

from __future__ import annotations

import re

from deepscout_core.domain.contracts import RequirementKind, ResearchContract

from deepscout_research.contracts.temporal_evidence import (
    evidence_supports_applicable_now,
    evidence_supports_enforcement_timing,
    evidence_supports_future_or_transitional,
)


def attribute_requirements(
    *,
    statement: str,
    quote: str,
    contract: ResearchContract,
) -> list[str]:
    matched: list[str] = []
    combined = f"{statement} {quote}".casefold()
    goal = contract.primary_question.casefold()

    for requirement in contract.requirements:
        req_id = requirement.requirement_id
        if req_id == "R0":
            if any(token in combined for token in _tokens(goal) if len(token) > 4):
                matched.append(req_id)
            continue
        if req_id == "R_compare":
            if _comparison_subjects_present(combined, goal):
                matched.append(req_id)
            continue
        if req_id in {"R_president"}:
            if ("president" in combined or "presidente" in combined) and (
                "commission" in combined or "commissione" in combined
            ):
                matched.append(req_id)
            continue
        if req_id == "R_gpai_guidance":
            if any(t in combined for t in ("gpai", "general purpose", "ai act", "modelli di ia")) and any(
                t in combined for t in ("guideline", "linee guida", "obligation", "obbligh", "transparency")
            ):
                matched.append(req_id)
            continue
        if req_id == "R_reg_now":
            if evidence_supports_applicable_now(statement=statement, quote=quote):
                matched.append(req_id)
            continue
        if req_id in {"R_reg_later", "R_reg_apply"}:
            if evidence_supports_future_or_transitional(statement=statement, quote=quote):
                matched.append(req_id)
            if req_id == "R_reg_apply" and evidence_supports_applicable_now(
                statement=statement, quote=quote
            ):
                matched.append(req_id)
            continue
        if req_id in {"R_reg_time", "R_timeline"}:
            if evidence_supports_enforcement_timing(statement=statement, quote=quote):
                matched.append(req_id)
            continue
        if requirement.kind == RequirementKind.QUANTIFICATION and re.search(r"\d", quote):
            matched.append(req_id)
            continue
        if requirement.kind == RequirementKind.COMPARISON and _comparison_subjects_present(combined, goal):
            matched.append(req_id)
            continue
        if requirement.kind == RequirementKind.TRADEOFF and any(
            token in combined for token in ("tradeoff", "trade-off", "vs", "compared", "confront")
        ):
            matched.append(req_id)
            continue
        if _token_overlap(statement, requirement.text, goal):
            matched.append(req_id)

    return list(dict.fromkeys(matched))[:10]


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", text.casefold())}


def _token_overlap(statement: str, requirement_text: str, goal: str) -> bool:
    claim_tokens = _tokens(statement)
    req_tokens = _tokens(requirement_text) | _tokens(goal)
    if not req_tokens:
        return False
    overlap = len(claim_tokens & req_tokens)
    return overlap >= max(2, min(4, len(req_tokens) // 6))


def _comparison_subjects_present(combined: str, goal: str) -> bool:
    pairs = [
        ("lfp", "nmc"),
        ("bev", "ice"),
        ("bev", "icev"),
        ("battery electric", "combustion"),
    ]
    for left, right in pairs:
        if left in goal and right in goal and left in combined and right in combined:
            return True
    if "confronta" in goal or "compare" in goal or "versus" in goal:
        return bool(re.search(r"\bvs\b|\bversus\b|compared to|confront", combined))
    return False
