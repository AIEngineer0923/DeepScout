"""Contradiction detection over normalized claims."""

from __future__ import annotations

import uuid

from deepscout_core.domain.enums import ClaimVerificationStatus, ContradictionEvidenceStatus
from deepscout_core.domain.schemas import ContradictionWrite
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

_OPPOSITE_MARKERS = (
    ("not ", " "),
    ("never ", " "),
    ("no ", " "),
    ("lower", "higher"),
    ("less", "more"),
    ("decrease", "increase"),
    ("worse", "better"),
    ("disadvantage", "advantage"),
)


def _normalized(statement: str) -> str:
    return " ".join(statement.lower().split())


def _may_contradict(a: str, b: str) -> str | None:
    norm_a = _normalized(a)
    norm_b = _normalized(b)
    if norm_a == norm_b:
        return None
    for left, right in _OPPOSITE_MARKERS:
        if left in norm_a and right in norm_b and left not in norm_b:
            return f"Opposition markers: {left.strip()} vs {right.strip()}"
        if left in norm_b and right in norm_a and left not in norm_a:
            return f"Opposition markers: {left.strip()} vs {right.strip()}"
    return None


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
            if claim_a.question_id is not None and claim_b.question_id != claim_a.question_id:
                continue
            reason = _may_contradict(claim_a.statement, claim_b.statement)
            if reason is None:
                continue
            store.add_contradiction(
                run_id,
                ContradictionWrite(
                    claim_a_id=claim_a.id,
                    claim_b_id=claim_b.id,
                    description=reason[:8000],
                    evidence_status=ContradictionEvidenceStatus.INSUFFICIENT_EVIDENCE,
                ),
            )
            created += 1
    return created
