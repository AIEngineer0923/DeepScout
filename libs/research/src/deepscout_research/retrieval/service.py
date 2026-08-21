"""Hybrid retrieval over the current run corpus only."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

from deepscout_core.settings import Settings
from deepscout_persistence.retrieval import dense_search, lexical_search, load_chunks
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.retrieval.embeddings import (
    EmbeddingSpec,
    build_embedding_client,
    embed_query,
)
from deepscout_research.retrieval.fusion import reciprocal_rank_fusion
from deepscout_research.retrieval.grader import grade_retrieval
from deepscout_research.retrieval.models import RetrievalQuery, RetrievedChunk
from deepscout_research.retrieval.rerank import rerank_candidates
from deepscout_research.retrieval.security import looks_like_injection, sanitize_retrieved_text
from deepscout_research.retrieval.strategy import resolve_strategy, strategy_to_mode


class CrossRunIsolationError(PermissionError):
    """Attempted retrieval against another run's corpus."""


class RetrievalService:
    def __init__(
        self,
        store: ResearchStore,
        settings: Settings,
        *,
        client=None,
        spec: EmbeddingSpec | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self.settings = settings
        if client is None or spec is None:
            client, spec = build_embedding_client(settings)
        self._client = client
        self._spec = spec

    @traceable(name="retrieve", run_type="retriever")
    def retrieve(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        ranked = self._search_once(request)
        grade = grade_retrieval(ranked, query=request.query)
        if not grade.sufficient and request.candidate_k < 40:
            widened = self._search_once(
                request.model_copy(update={"candidate_k": min(request.candidate_k * 2, 40)})
            )
            if widened:
                return widened[: request.top_k]
        return ranked

    def _search_once(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        run = self._store.get_run(request.run_id)
        if run is None:
            raise LookupError(f"ResearchRun {request.run_id} not found")
        session = self._store._session
        source_ids = request.source_ids or None
        dense_ranked: list[uuid.UUID] = []
        lexical_ranked: list[uuid.UUID] = []
        dense_scores: dict[uuid.UUID, float] = {}
        lexical_scores: dict[uuid.UUID, float] = {}
        strategy = resolve_strategy(self._settings)
        mode = request.mode if request.mode in {"dense", "lexical", "hybrid"} else strategy_to_mode(strategy)

        # Overlap provider embedding wait with local FTS. The SQLAlchemy session
        # stays on this thread; only embed_query runs off-thread.
        embed_future = None
        executor: ThreadPoolExecutor | None = None
        if mode in {"dense", "hybrid"}:
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rag-embed")
            embed_future = executor.submit(embed_query, self._client, request.query)

        if mode in {"lexical", "hybrid"}:
            lexical_hits = lexical_search(
                session,
                run_id=request.run_id,
                query=request.query,
                limit=request.candidate_k,
                source_ids=source_ids,
            )
            lexical_ranked = [item_id for item_id, _ in lexical_hits]
            lexical_scores = {item_id: score for item_id, score in lexical_hits}

        if embed_future is not None:
            try:
                vector = embed_future.result()
            finally:
                if executor is not None:
                    executor.shutdown(wait=False)
            if len(vector) != self._spec.dimensions:
                raise ValueError("query embedding dimension does not match stored space")
            dense_hits = dense_search(
                session,
                run_id=request.run_id,
                query_vector=vector,
                provider=self._spec.provider,
                model=self._spec.model,
                dimensions=self._spec.dimensions,
                config_version=self._spec.config_version,
                limit=request.candidate_k,
                source_ids=source_ids,
            )
            dense_ranked = [item_id for item_id, _ in dense_hits]
            dense_scores = {item_id: score for item_id, score in dense_hits}

        lists = [item for item in (dense_ranked, lexical_ranked) if item]
        fused = reciprocal_rank_fusion(lists) if lists else {}
        ordered_ids = sorted(fused, key=fused.get, reverse=True)
        rows = load_chunks(session, ordered_ids)
        snapshots = {row.id: row for row in self._store.list_snapshots_for_run(request.run_id)}
        candidates: list[RetrievedChunk] = []
        for chunk_id in ordered_ids:
            row = rows.get(chunk_id)
            if row is None:
                continue
            if row.research_run_id != request.run_id:
                raise CrossRunIsolationError("chunk run_id mismatch")
            snapshot = snapshots.get(row.source_snapshot_id)
            if snapshot is None or snapshot.source_id != row.source_id:
                continue
            if request.fresher_than and snapshot.retrieved_at and snapshot.retrieved_at < request.fresher_than:
                continue
            dense_rank = dense_ranked.index(chunk_id) + 1 if chunk_id in dense_ranked else None
            lexical_rank = lexical_ranked.index(chunk_id) + 1 if chunk_id in lexical_ranked else None
            text = sanitize_retrieved_text(row.text)
            candidates.append(
                RetrievedChunk(
                    chunk_id=row.id,
                    snapshot_id=row.source_snapshot_id,
                    source_id=row.source_id,
                    run_id=row.research_run_id,
                    text=text,
                    locator=f"snapshot:{row.source_snapshot_id}:offset:{row.start_offset}-{row.end_offset}",
                    ordinal=row.ordinal,
                    start_offset=row.start_offset,
                    end_offset=row.end_offset,
                    dense_score=dense_scores.get(chunk_id),
                    lexical_score=lexical_scores.get(chunk_id),
                    fused_score=fused.get(chunk_id, 0.0),
                    dense_rank=dense_rank,
                    lexical_rank=lexical_rank,
                    retrieved_at=snapshot.retrieved_at,
                    section_title=row.section_title,
                    retrieval_reason="injection-flagged" if looks_like_injection(text) else "",
                )
            )
        if not request.apply_rerank:
            return candidates[: request.top_k]
        return rerank_candidates(candidates, query=request.query, limit=request.top_k)
