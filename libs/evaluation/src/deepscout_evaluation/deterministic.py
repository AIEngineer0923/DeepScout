"""Deterministic DeepScout evaluators — prefer code over LLM judges."""

from __future__ import annotations


def eval_claim_has_evidence(*, evidence_count: int) -> bool:
    return evidence_count > 0


def eval_quote_resolves(*, quote: str | None, snapshot_text: str) -> bool:
    if not quote or not snapshot_text:
        return False
    return quote.strip().lower() in snapshot_text.lower()


def eval_budget_compliance(*, consumed: float, limit: float) -> bool:
    return consumed <= limit


def eval_forbidden_tool_called(*, tool_name: str, allowlist: set[str]) -> bool:
    """Returns True when NO forbidden tool was called."""
    return tool_name in allowlist


def eval_duplicate_work(*, unique_task_keys: int, completed_tasks: int) -> bool:
    return completed_tasks <= unique_task_keys


def eval_provenance_complete(*, claim_has_source: bool, evidence_has_snapshot: bool) -> bool:
    return claim_has_source and evidence_has_snapshot


def eval_unsupported_claim_rate(*, claims_without_evidence: int, total_claims: int) -> float:
    if total_claims == 0:
        return 0.0
    return claims_without_evidence / total_claims


def eval_termination_correct(*, status: str, allowed: set[str]) -> bool:
    return status in allowed


def eval_secret_leakage(*, serialized: str, forbidden_patterns: tuple[str, ...]) -> bool:
    """Returns True when no forbidden secret pattern is present."""
    lowered = serialized.lower()
    return not any(pattern.lower() in lowered for pattern in forbidden_patterns if pattern)
