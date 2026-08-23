"""Map verified claims and evidence to ResearchContract requirement IDs."""

from __future__ import annotations

import re

from deepscout_core.domain.contracts import RequirementKind, ResearchContract

from deepscout_research.contracts.temporal_evidence import (
    evidence_supports_applicable_now,
    evidence_supports_enforcement_timing,
    evidence_supports_future_or_transitional,
)
from deepscout_research.contracts.text_normalize import normalized_research_tokens


def attribute_requirements(
    *,
    statement: str,
    quote: str,
    contract: ResearchContract,
) -> list[str]:
    matched: list[str] = []
    combined = f"{statement} {quote}".casefold()
    for requirement in contract.requirements:
        req_id = requirement.requirement_id
        if req_id == "R0":
            continue
        if req_id == "R_compare":
            if _comparison_requirement_satisfied(combined, requirement):
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
        if requirement.kind == RequirementKind.QUANTIFICATION and re.search(r"\d", quote) and _token_overlap(
            statement, requirement.text
        ):
            matched.append(req_id)
            continue
        if requirement.kind == RequirementKind.COMPARISON and _comparison_requirement_satisfied(
            combined, requirement
        ):
            matched.append(req_id)
            continue
        if requirement.kind == RequirementKind.TRADEOFF and any(
            token in combined for token in ("tradeoff", "trade-off", "vs", "compared", "confront")
        ):
            matched.append(req_id)
            continue
        if requirement.kind in {RequirementKind.SOURCE_POLICY, RequirementKind.OUTPUT_FORMAT}:
            continue
        if _token_overlap(f"{statement} {quote}", requirement.text):
            matched.append(req_id)

    return list(dict.fromkeys(matched))[:10]


def requirements_for_query(*, query: str, contract: ResearchContract) -> list[str]:
    """Recover requirement provenance from a requirement-scoped search query."""
    query_tokens = _meaningful_tokens(query)
    matched: list[str] = []
    for requirement in contract.requirements:
        if requirement.requirement_id == "R0" or requirement.kind in {
            RequirementKind.OUTPUT_FORMAT,
            RequirementKind.SOURCE_POLICY,
            RequirementKind.SYNTHESIS,
        }:
            continue
        requirement_tokens = _meaningful_tokens(requirement.text)
        if not requirement_tokens:
            continue
        overlap = len(query_tokens & requirement_tokens)
        minimum = 1 if len(requirement_tokens) <= 2 else 2
        if overlap >= minimum and overlap / len(requirement_tokens) >= 0.5:
            matched.append(requirement.requirement_id)
    return matched[:10]


def _tokens(text: str) -> set[str]:
    return normalized_research_tokens(text)


_STOPWORDS = {
    "about",
    "across",
    "after",
    "also",
    "between",
    "della",
    "delle",
    "degli",
    "dello",
    "from",
    "into",
    "nella",
    "nelle",
    "quali",
    "questo",
    "rispetto",
    "that",
    "their",
    "these",
    "those",
    "what",
    "when",
    "which",
    "with",
}


def _meaningful_tokens(text: str) -> set[str]:
    return {token for token in _tokens(text) if token not in _STOPWORDS}


def _token_overlap(statement: str, requirement_text: str) -> bool:
    claim_tokens = _tokens(statement)
    req_tokens = _meaningful_tokens(requirement_text)
    if not req_tokens:
        return False
    overlap = len(claim_tokens & req_tokens)
    minimum = 2 if len(req_tokens) <= 8 else 3
    return overlap >= minimum and overlap / len(req_tokens) >= 0.18


def _subject_present(
    combined: str,
    subject: str,
    *,
    excluded_tokens: set[str] | None = None,
) -> bool:
    tokens = _meaningful_tokens(subject)
    tokens -= excluded_tokens or set()
    if not tokens:
        return False
    combined_tokens = _tokens(combined)
    if tokens & combined_tokens:
        return True
    compact = re.sub(r"[^A-Za-z0-9]", "", subject)
    if not (2 <= len(compact) <= 8 and compact.isupper()):
        return False
    words = re.findall(r"[a-z]+", combined.casefold())
    for start in range(len(words)):
        initials = ""
        for word in words[start : start + len(compact)]:
            initials += word[0]
            if len(initials) >= 2 and compact.casefold().startswith(initials):
                return True
    return False


def _comparison_requirement_satisfied(combined: str, requirement) -> bool:
    subjects = requirement.comparison_subjects
    if len(subjects) >= 2:
        token_sets = [_meaningful_tokens(subject) for subject in subjects[:2]]
        common = token_sets[0] & token_sets[1]
        return all(
            _subject_present(combined, subject, excluded_tokens=common)
            for subject in subjects[:2]
        ) and bool(
            re.search(
                r"\bvs\b|\bversus\b|compared|comparison|confront|relative to|than\b|whereas|while",
                combined,
            )
        )
    return _token_overlap(combined, requirement.text) and bool(
        re.search(
            r"\bvs\b|\bversus\b|compared|comparison|confront|relative to|than\b|whereas|while",
            combined,
        )
    )
