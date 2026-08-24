"""Reciprocal Rank Fusion — ranks, never raw scores."""

from __future__ import annotations

from uuid import UUID

from deepscout_research.retrieval.spec import RRF_K


def reciprocal_rank_fusion(
    ranked_lists: list[list[UUID]],
    *,
    k: int = RRF_K,
    weights: list[float] | None = None,
) -> dict[UUID, float]:
    if weights is not None and len(weights) != len(ranked_lists):
        raise ValueError("RRF weights must align with ranked lists")
    fused: dict[UUID, float] = {}
    for list_index, ranked in enumerate(ranked_lists):
        weight = weights[list_index] if weights is not None else 1.0
        seen: set[UUID] = set()
        for rank, item_id in enumerate(ranked, start=1):
            if item_id in seen:
                continue
            seen.add(item_id)
            fused[item_id] = fused.get(item_id, 0.0) + weight / (k + rank)
    return fused
