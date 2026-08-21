"""Retrieval-specific deterministic metrics."""

from __future__ import annotations

import math


def recall_at_k(*, relevant_found: int, total_relevant: int, k: int) -> float:
    if total_relevant == 0:
        return 0.0
    return min(relevant_found, k) / total_relevant


def precision_at_k(*, relevant_found: int, returned: int, k: int) -> float:
    if returned == 0:
        return 0.0
    return min(relevant_found, k) / min(returned, k)


def mrr(*, first_relevant_rank: int | None) -> float:
    if first_relevant_rank is None or first_relevant_rank <= 0:
        return 0.0
    return 1.0 / first_relevant_rank


def hit_at_k(*, relevant_found: int, k: int) -> float:
    del k
    return 1.0 if relevant_found > 0 else 0.0


def ndcg_at_k(*, gains: list[float], k: int) -> float:
    """Binary/graded NDCG@K over the first k ranks (gain list already ordered)."""
    trimmed = gains[:k]
    if not trimmed:
        return 0.0
    dcg = sum(gain / math.log2(idx + 2) for idx, gain in enumerate(trimmed))
    ideal = sorted(trimmed, reverse=True)
    idcg = sum(gain / math.log2(idx + 2) for idx, gain in enumerate(ideal))
    if idcg <= 0.0:
        return 0.0
    return dcg / idcg


def duplicate_candidate_rate(*, total: int, unique_snapshots: int) -> float:
    if total == 0:
        return 0.0
    return 1.0 - (unique_snapshots / total)
