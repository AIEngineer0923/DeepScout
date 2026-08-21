"""Explicit retrieval strategy policy — no scattered deep_mode branches."""

from __future__ import annotations

from enum import StrEnum

from deepscout_core.settings import Settings


class RetrievalStrategy(StrEnum):
    DIRECT = "direct"
    LEXICAL = "lexical"
    DENSE = "dense"
    HYBRID = "hybrid"
    HYBRID_RERANKED = "hybrid_reranked"
    MULTI_QUERY_HYBRID = "multi_query_hybrid"
    HIERARCHICAL = "hierarchical"
    ADAPTIVE = "adaptive"


def resolve_strategy(settings: Settings) -> RetrievalStrategy:
    mode = settings.retrieval_mode.lower()
    if mode == "lexical":
        return RetrievalStrategy.LEXICAL
    if mode == "dense":
        return RetrievalStrategy.DENSE
    if mode == "hybrid":
        return RetrievalStrategy.HYBRID_RERANKED
    return RetrievalStrategy.HYBRID_RERANKED


def strategy_to_mode(strategy: RetrievalStrategy) -> str:
    match strategy:
        case RetrievalStrategy.LEXICAL:
            return "lexical"
        case RetrievalStrategy.DENSE:
            return "dense"
        case _:
            return "hybrid"
