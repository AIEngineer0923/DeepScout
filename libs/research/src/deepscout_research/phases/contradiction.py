"""Contradiction detection with trade-off vs true contradiction classification."""

from __future__ import annotations

import re
import uuid

from deepscout_core.domain.enums import ClaimVerificationStatus, ContradictionEvidenceStatus
from deepscout_core.domain.schemas import ContradictionWrite
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

_TRADEOFF_DIMENSIONS = (
    ("energy density", "thermal safety"),
    ("energy density", "cycle life"),
    ("cost", "performance"),
    ("safety", "energy density"),
    ("weight", "range"),
    ("power", "durability"),
)

_SCOPE_MARKERS = ("global", "europe", "eu", "us", "cell level", "pack level", "2024", "2025", "2026")
_METHOD_MARKERS = ("methodology", "assumption", "model", "scenario", "grid mix", "lifetime", "recycling")


def _normalized(statement: str) -> str:
    return " ".join(statement.lower().split())


def _token_set(statement: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", statement.lower())}


def _shared_subject(a: str, b: str) -> bool:
    tokens_a = _token_set(a)
    tokens_b = _token_set(b)
    if not tokens_a or not tokens_b:
        return False
    overlap = tokens_a & tokens_b
    return len(overlap) >= max(2, min(4, len(tokens_a) // 6))


def _is_tradeoff(a: str, b: str) -> bool:
    norm_a = _normalized(a)
    norm_b = _normalized(b)
    for left, right in _TRADEOFF_DIMENSIONS:
        if (left in norm_a and right in norm_b) or (left in norm_b and right in norm_a):
            return True
    if not _shared_subject(a, b):
        return True
    return False


def _scope_or_method_difference(a: str, b: str) -> str | None:
    norm_a = _normalized(a)
    norm_b = _normalized(b)
    for marker in _SCOPE_MARKERS:
        if marker in norm_a and marker not in norm_b:
            return f"Scope difference: {marker}"
        if marker in norm_b and marker not in norm_a:
            return f"Scope difference: {marker}"
    for marker in _METHOD_MARKERS:
        if marker in norm_a and marker not in norm_b:
            return f"Methodological difference: {marker}"
        if marker in norm_b and marker not in norm_a:
            return f"Methodological difference: {marker}"
    return None


def _polarity_conflict(a: str, b: str) -> str | None:
    norm_a = _normalized(a)
    norm_b = _normalized(b)
    if norm_a == norm_b:
        return None
    neg_a = (" not ", " never ", " no ") if any(x in norm_a for x in (" not ", " never ", " no ")) else ()
    neg_b = (" not ", " never ", " no ") if any(x in norm_b for x in (" not ", " never ", " no ")) else ()
    if neg_a and not neg_b and _shared_subject(a, b):
        return "Semantic disagreement: negation vs affirmation"
    if neg_b and not neg_a and _shared_subject(a, b):
        return "Semantic disagreement: negation vs affirmation"

    pairs = (
        ("lower", "higher"),
        ("less", "more"),
        ("decrease", "increase"),
        ("worse", "better"),
        ("cannot", "can"),
        ("prohibited", "allowed"),
    )
    for left, right in pairs:
        if left in norm_a and right in norm_b and _shared_subject(a, b):
            if _is_tradeoff(a, b):
                return None
            return f"Opposing values on comparable proposition: {left} vs {right}"
        if left in norm_b and right in norm_a and _shared_subject(a, b):
            if _is_tradeoff(a, b):
                return None
            return f"Opposing values on comparable proposition: {left} vs {right}"
    return None


def _classify_pair(a: str, b: str) -> str | None:
    if _is_tradeoff(a, b):
        return None
    scope = _scope_or_method_difference(a, b)
    if scope:
        return scope
    return _polarity_conflict(a, b)


@traceable(name="phase:contradiction", run_type="chain")
def detect_contradictions_for_run(store: ResearchStore, run_id: uuid.UUID) -> int:
    claims = [
        claim
        for claim in store.list_claims(run_id)
        if claim.verification_status
        in {
            ClaimVerificationStatus.VERIFIED,
            ClaimVerificationStatus.PARTIALLY_VERIFIED,
            ClaimVerificationStatus.SUPPORTED,
        }
    ]
    created = 0
    for index, claim_a in enumerate(claims):
        for claim_b in claims[index + 1 :]:
            reason = _classify_pair(claim_a.statement, claim_b.statement)
            if reason is None:
                continue
            store.add_contradiction(
                run_id,
                ContradictionWrite(
                    claim_a_id=claim_a.id,
                    claim_b_id=claim_b.id,
                    description=reason[:8000],
                    evidence_status=ContradictionEvidenceStatus.SUFFICIENT,
                ),
            )
            created += 1
    return created
