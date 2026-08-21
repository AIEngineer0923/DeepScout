"""Reciprocal Rank Fusion — ranks, never raw scores."""

from __future__ import annotations

from uuid import UUID

from deepscout_research.retrieval.spec import RRF_K


def reciprocal_rank_fusion(
    ranked_lists: list[list[UUID]],
    *,
    k: int = RRF_K,
) -> dict[UUID, float]:
    fused: dict[UUID, float] = {}
    for ranked in ranked_lists:
        seen: set[UUID] = set()
        for rank, item_id in enumerate(ranked, start=1):
            if item_id in seen:
                continue
            seen.add(item_id)
            fused[item_id] = fused.get(item_id, 0.0) + 1.0 / (k + rank)
    return fused
