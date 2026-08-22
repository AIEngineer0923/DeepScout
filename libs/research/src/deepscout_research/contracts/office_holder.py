"""Authoritative office-holder extraction and verification."""

from __future__ import annotations

import re

from deepscout_core.domain.contracts import OfficeHolderEvidence, VerifiedEntity

_NAME_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+(?:[a-z]+|[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?)){1,4})\b"
)
_PRESIDENT_CONTEXT_RE = re.compile(
    r"([A-Z][a-z]+(?:\s+(?:[a-z]+|[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?)){1,4})\s+(?:is|è)\s+"
    r"(?:the\s+)?(?:President|Presidente)",
    re.I,
)
_CURRENT_INDICATORS = (
    "current",
    "attualmente",
    "is president",
    "è presidente",
    "president of the european commission",
    "presidente della commissione europea",
    "president of the commission",
)
_HISTORICAL_INDICATORS = (
    "former",
    "ex-president",
    "was president",
    "era presidente",
    "previously served",
    "ex presidente",
)


_HEADING_NAME_RE = re.compile(
    r"(?:^|\n)\s*([A-Z][a-z]+(?:\s+(?:[a-z]+|[A-Z][a-z'-]+)){1,4})\s*(?:\n|$)",
    re.M,
)


def extract_office_holder_evidence(
    text: str,
    *,
    source_url: str,
    office_title: str = "President of the European Commission",
) -> OfficeHolderEvidence | None:
    best: OfficeHolderEvidence | None = None
    if "president" in text.casefold() and "commission" in text.casefold():
        for match in _HEADING_NAME_RE.finditer(text):
            name = match.group(1).strip()
            context = text[match.start() : match.start() + 400]
            lowered = context.casefold()
            if "president" not in lowered and "presidente" not in lowered:
                continue
            candidate = OfficeHolderEvidence(
                person_name=name,
                office_title=office_title,
                institution="European Commission",
                current_role_indicator=True,
                evidence_span=context[:2000],
                source_url=source_url[:2048],
            )
            if verify_office_holder(candidate):
                return candidate
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        lowered = sentence.casefold()
        if "president" not in lowered and "presidente" not in lowered:
            continue
        if "commission" not in lowered and "commissione" not in lowered:
            continue
        if any(token in lowered for token in _HISTORICAL_INDICATORS):
            continue
        name_match = _PRESIDENT_CONTEXT_RE.search(sentence) or _NAME_RE.search(sentence)
        if name_match is None:
            continue
        name = name_match.group(1).strip()
        if name.casefold() in {"european commission", "european union", "commission european"}:
            continue
        current = any(token in lowered for token in _CURRENT_INDICATORS) or (
            "president" in lowered and not any(token in lowered for token in _HISTORICAL_INDICATORS)
        )
        candidate = OfficeHolderEvidence(
            person_name=name,
            office_title=office_title,
            institution="European Commission",
            current_role_indicator=current,
            evidence_span=sentence[:2000],
            source_url=source_url[:2048],
        )
        if verify_office_holder(candidate):
            best = candidate
            break
    return best


def verify_office_holder(evidence: OfficeHolderEvidence) -> bool:
    if not evidence.person_name or len(evidence.person_name.split()) < 2:
        return False
    disallowed = {
        "president",
        "presidente",
        "european commission",
        "commissione europea",
        "the commission",
    }
    if evidence.person_name.casefold() in disallowed:
        return False
    if not evidence.current_role_indicator:
        return False
    lowered = evidence.evidence_span.casefold()
    if any(token in lowered for token in _HISTORICAL_INDICATORS):
        return False
    if "president" not in lowered and "presidente" not in lowered:
        return False
    if "commission" not in lowered and "commissione" not in lowered:
        return False
    return len(evidence.evidence_span) >= 25


def to_verified_entity(evidence: OfficeHolderEvidence, *, task_key: str, evidence_id: str) -> VerifiedEntity:
    return VerifiedEntity(
        name=evidence.person_name,
        role=evidence.office_title,
        institution=evidence.institution,
        evidence_id=evidence_id,
        source_url=evidence.source_url,
        task_key=task_key,
    )


def office_title_from_goal(goal: str) -> str:
    lowered = goal.casefold()
    if "presidente della commissione europea" in lowered or "president of the european commission" in lowered:
        return "President of the European Commission"
    if "president" in lowered or "presidente" in lowered:
        return "current office-holder"
    return "current office-holder"
