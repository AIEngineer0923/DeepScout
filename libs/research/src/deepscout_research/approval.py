"""Human approval security — model/retrieved text cannot grant approval."""

from __future__ import annotations

import re
from enum import StrEnum


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# Patterns that must never be treated as authoritative approval signals.
_SPOOF_PATTERNS = (
    re.compile(r"human\s*approved", re.I),
    re.compile(r"\bapproved\s+this\b", re.I),
    re.compile(r"approval\s*=\s*true", re.I),
    re.compile(r"skip\s+human\s+review", re.I),
    re.compile(r"resume\s+automatically", re.I),
    re.compile(r"raise\s+budget", re.I),
    re.compile(r"grant\s+tool\s+access", re.I),
)


def text_claims_approval(text: str) -> bool:
    """True if untrusted text *claims* approval — never treat as real approval."""
    return any(p.search(text) for p in _SPOOF_PATTERNS)


def is_authoritative_approval(
    *,
    decision: ApprovalDecision | None,
    source: str,
    untrusted_payload: str | None = None,
) -> bool:
    """Approval is authoritative only from application/API sources, never content."""
    if source not in {"api", "ui", "operator"}:
        return False
    if decision is not ApprovalDecision.APPROVED:
        return False
    if untrusted_payload is not None and text_claims_approval(untrusted_payload):
        # Spoof strings in payload are DATA; they do not flip the decision — but
        # the decision itself must still come from source=api/ui/operator.
        pass
    return True
