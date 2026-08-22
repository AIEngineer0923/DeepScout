"""Adaptive retrieval routing — selects retriever mix from query characteristics."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from typing import Literal as TypingLiteral

from pydantic import BaseModel, Field

from deepscout_research.retrieval.planner import QueryPlan, RetrievalRoute

ResearchModeName = TypingLiteral["quick", "standard", "deep"]


class QueryIntent(StrEnum):
    IDENTIFIER = "identifier"
    SEMANTIC = "semantic"
    ENTITY_RELATION = "entity_relation"
    LONG_CONTEXT = "long_context"
    GLOBAL_THEMATIC = "global_thematic"
    MIXED = "mixed"


class RetrievalRoutePlan(BaseModel):
    """Executable routing decision — persisted in trace metadata."""

    intent: QueryIntent
    mode: Literal["dense", "lexical", "hybrid"] = "hybrid"
    use_bm25: bool = True
    use_fts: bool = True
    use_dense: bool = True
    use_compiled: bool = False
    use_graph: bool = False
    skip_retrieval: bool = False
    top_k: int = Field(ge=1, le=32)
    candidate_k: int = Field(ge=1, le=64)
    reason: str = ""


_GLOBAL_HINTS = (
    "overall",
    "landscape",
    "across sources",
    "themes",
    "summarize the corpus",
    "what do we know",
)
_ENTITY_HINTS = (
    "relationship",
    "related to",
    "connected",
    "between",
    "versus",
    "vs ",
)


def classify_intent(plan: QueryPlan) -> QueryIntent:
    if plan.skip_retrieval:
        return QueryIntent.LONG_CONTEXT
    lowered = plan.original_query.lower()
    if plan.corpus == "compiled":
        return QueryIntent.GLOBAL_THEMATIC
    if plan.corpus == "both":
        return QueryIntent.MIXED
    if plan.entities and len(plan.entities) >= 2:
        return QueryIntent.ENTITY_RELATION
    if plan.entities:
        return QueryIntent.IDENTIFIER
    if any(hint in lowered for hint in _ENTITY_HINTS):
        return QueryIntent.ENTITY_RELATION
    if any(hint in lowered for hint in _GLOBAL_HINTS):
        return QueryIntent.GLOBAL_THEMATIC
    return QueryIntent.SEMANTIC


def route_retrieval(
    plan: QueryPlan,
    *,
    research_mode: ResearchModeName = "standard",
    router_enabled: bool = True,
) -> RetrievalRoutePlan:
    intent = classify_intent(plan)
    if not router_enabled:
        return RetrievalRoutePlan(
            intent=intent,
            mode=plan.mode,
            use_bm25=True,
            use_fts=True,
            use_dense=plan.mode in {"dense", "hybrid"},
            use_compiled=plan.corpus in {"compiled", "both"},
            use_graph=plan.corpus in {"compiled", "both"},
            skip_retrieval=plan.skip_retrieval,
            top_k=plan.top_k,
            candidate_k=plan.candidate_k,
            reason="router_disabled",
        )

    mode = plan.mode
    use_bm25 = True
    use_fts = True
    use_dense = True
    use_compiled = plan.corpus in {"compiled", "both"}
    use_graph = False
    reason_parts: list[str] = [f"intent={intent.value}"]

    match intent:
        case QueryIntent.IDENTIFIER:
            mode = "lexical" if plan.mode == "lexical" else "hybrid"
            use_dense = plan.mode != "lexical"
            use_bm25 = True
            use_fts = True
            reason_parts.append("identifier:bm25+fts_heavy")
        case QueryIntent.SEMANTIC:
            mode = "hybrid" if plan.mode == "hybrid" else plan.mode
            use_dense = plan.mode != "lexical"
            reason_parts.append("semantic:dense_heavy_hybrid")
        case QueryIntent.ENTITY_RELATION:
            mode = "hybrid"
            use_compiled = True
            use_graph = True
            reason_parts.append("entity_relation:hybrid+graph+compiled")
        case QueryIntent.GLOBAL_THEMATIC:
            use_compiled = True
            use_graph = True
            use_dense = plan.mode != "lexical"
            reason_parts.append("global:compiled+graph")
        case QueryIntent.MIXED:
            use_compiled = True
            use_graph = True
            reason_parts.append("mixed:raw+compiled")
        case QueryIntent.LONG_CONTEXT:
            return RetrievalRoutePlan(
                intent=intent,
                mode=plan.mode,
                skip_retrieval=True,
                top_k=plan.top_k,
                candidate_k=plan.candidate_k,
                reason=plan.skip_reason or "long_context_path",
            )

    top_k, candidate_k = _scale_budget(plan.top_k, plan.candidate_k, research_mode)
    if RetrievalRoute.LEXICAL in plan.routes and intent == QueryIntent.IDENTIFIER:
        candidate_k = min(candidate_k + 8, 64)

    return RetrievalRoutePlan(
        intent=intent,
        mode=mode,
        use_bm25=use_bm25,
        use_fts=use_fts,
        use_dense=use_dense,
        use_compiled=use_compiled,
        use_graph=use_graph,
        skip_retrieval=plan.skip_retrieval,
        top_k=top_k,
        candidate_k=candidate_k,
        reason=";".join(reason_parts),
    )


def _scale_budget(top_k: int, candidate_k: int, mode: ResearchModeName) -> tuple[int, int]:
    if mode == "quick":
        return min(top_k, 6), min(candidate_k, 16)
    if mode == "deep":
        return min(top_k + 4, 24), min(candidate_k + 12, 64)
    return top_k, candidate_k
