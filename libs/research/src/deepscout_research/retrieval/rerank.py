"""Deterministic post-fusion ranking — no model, no invented content."""

from __future__ import annotations

from collections import defaultdict

from deepscout_research.retrieval.models import RetrievedChunk
from deepscout_research.retrieval.spec import MAX_CHUNKS_PER_SOURCE


def rerank_candidates(
    candidates: list[RetrievedChunk],
    *,
    query: str,
    max_per_source: int = MAX_CHUNKS_PER_SOURCE,
    limit: int,
) -> list[RetrievedChunk]:
    query_tokens = {token.lower() for token in query.split() if len(token) >= 3}
    scored: list[tuple[float, RetrievedChunk]] = []
    for item in candidates:
        exact = sum(1 for token in query_tokens if token in item.text.lower())
        recency = 0.0
        if item.retrieved_at is not None:
            recency = item.retrieved_at.timestamp() / 1e12
        score = item.fused_score + 0.02 * exact + recency
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    per_source: dict[str, int] = defaultdict(int)
    selected: list[RetrievedChunk] = []
    overflow: list[RetrievedChunk] = []
    for score, item in scored:
        count = per_source[str(item.source_id)]
        updated = item.model_copy(update={"rerank_score": score, "retrieval_reason": _reason(item, query_tokens)})
        if count >= max_per_source:
            overflow.append(updated)
            continue
        per_source[str(item.source_id)] = count + 1
        selected.append(updated)
        if len(selected) >= limit:
            return selected
    for item in overflow:
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected[:limit]


def _reason(item: RetrievedChunk, query_tokens: set[str]) -> str:
    parts = []
    if item.dense_rank is not None:
        parts.append(f"dense@{item.dense_rank}")
    if item.lexical_rank is not None:
        parts.append(f"lexical@{item.lexical_rank}")
    if any(token in item.text.lower() for token in query_tokens):
        parts.append("exact-token")
    return ",".join(parts) or "fused"
