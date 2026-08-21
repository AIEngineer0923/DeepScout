"""Deterministic retrieval quality gate — relevance, not factual support."""

from __future__ import annotations

from dataclasses import dataclass

from deepscout_research.retrieval.models import RetrievedChunk


@dataclass(frozen=True, slots=True)
class RetrievalGrade:
    sufficient: bool
    selected_count: int
    duplicate_rate: float
    source_count: int
    reason: str


def grade_retrieval(
    candidates: list[RetrievedChunk],
    *,
    query: str,
    min_results: int = 1,
    max_duplicate_rate: float = 0.5,
) -> RetrievalGrade:
    if not candidates:
        return RetrievalGrade(
            sufficient=False,
            selected_count=0,
            duplicate_rate=0.0,
            source_count=0,
            reason="no_candidates",
        )
    query_tokens = {token.lower() for token in query.split() if len(token) >= 3}
    relevant = [
        item
        for item in candidates
        if item.fused_score > 0 or any(token in item.text.lower() for token in query_tokens)
    ]
    unique_snapshots = {str(item.snapshot_id) for item in relevant}
    duplicate_rate = 1.0 - (len(unique_snapshots) / max(len(relevant), 1))
    source_count = len({str(item.source_id) for item in relevant})
    sufficient = len(relevant) >= min_results and duplicate_rate <= max_duplicate_rate
    reason = "ok" if sufficient else "insufficient_or_duplicated"
    return RetrievalGrade(
        sufficient=sufficient,
        selected_count=len(relevant),
        duplicate_rate=round(duplicate_rate, 3),
        source_count=source_count,
        reason=reason,
    )
