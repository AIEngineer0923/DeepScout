"""Retrieval diagnostic trace — developer/evaluation only, not end-user facing."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_research.retrieval.models import RetrievedChunk
from deepscout_research.retrieval.planner import QueryPlan
from deepscout_research.retrieval.router import RetrievalRoutePlan
from pydantic import BaseModel, Field


class RetrievalCandidateDiagnostic(BaseModel):
    chunk_id: UUID | None = None
    source_id: UUID | None = None
    provenance_kind: str = "chunk"
    bm25_rank: int | None = None
    lexical_rank: int | None = None
    dense_rank: int | None = None
    fused_score: float | None = None
    rerank_score: float | None = None
    retrieval_reason: str = ""
    rejected: bool = False
    rejection_reason: str = ""


class RetrievalDiagnosticTrace(BaseModel):
    """Reconstructable retrieval decision trace for regression diagnosis."""

    query: str
    planned_query: str = ""
    detected_intent: str = ""
    selected_corpus: str = "raw"
    strategies: dict[str, bool] = Field(default_factory=dict)
    top_k: int = 0
    candidate_k: int = 0
    skip_retrieval: bool = False
    route_reason: str = ""
    candidates: list[RetrievalCandidateDiagnostic] = Field(default_factory=list)
    final_chunk_ids: list[str] = Field(default_factory=list)
    failure_class_hint: str | None = None

    @classmethod
    def from_plan_and_hits(
        cls,
        *,
        query: str,
        plan: QueryPlan,
        route: RetrievalRoutePlan,
        hits: list[RetrievedChunk],
        source_to_doc: dict[UUID, str] | None = None,
    ) -> RetrievalDiagnosticTrace:
        del source_to_doc
        candidates = [
            RetrievalCandidateDiagnostic(
                chunk_id=h.chunk_id,
                source_id=h.source_id,
                provenance_kind=h.provenance_kind,
                bm25_rank=h.bm25_rank,
                lexical_rank=h.lexical_rank,
                dense_rank=h.dense_rank,
                fused_score=h.fused_score,
                rerank_score=h.rerank_score,
                retrieval_reason=h.retrieval_reason,
            )
            for h in hits
        ]
        return cls(
            query=query,
            planned_query=plan.semantic_query,
            detected_intent=route.intent.value,
            selected_corpus=plan.corpus,
            strategies={
                "bm25": route.use_bm25,
                "fts": route.use_fts,
                "dense": route.use_dense,
                "compiled": route.use_compiled,
                "graph": route.use_graph,
            },
            top_k=route.top_k,
            candidate_k=route.candidate_k,
            skip_retrieval=route.skip_retrieval,
            route_reason=route.reason,
            candidates=candidates,
            final_chunk_ids=[str(h.chunk_id) for h in hits],
        )


def infer_retrieval_failure_class(
    *,
    case: dict[str, Any],
    trace: RetrievalDiagnosticTrace,
    metrics: dict[str, float],
) -> str | None:
    """Heuristic stage classifier — supplements human-labeled failure_class on fixtures."""
    if case.get("expected_intent") and trace.detected_intent != case["expected_intent"]:
        return "routing_failure"
    if case.get("should_answer") is False and metrics.get("hit_at_3", 0) > 0:
        return "no_answer_false_positive"
    if case.get("should_answer") is True and metrics.get("hit_at_3", 0) == 0:
        if not any(c.bm25_rank is not None for c in trace.candidates):
            return "lexical_retrieval_failure"
        if not any(c.dense_rank is not None for c in trace.candidates):
            return "dense_retrieval_failure"
        return "fusion_failure"
    if case.get("should_use_compiled") and not any(
        c.provenance_kind == "compiled" for c in trace.candidates
    ):
        return "compiled_knowledge_failure"
    if case.get("should_use_graph") and not any(
        c.retrieval_reason.startswith("graph:") for c in trace.candidates
    ):
        return "graph_retrieval_failure"
    return case.get("failure_class")
