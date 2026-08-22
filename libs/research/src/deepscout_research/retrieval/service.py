"""Hybrid retrieval over the current run corpus only."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

from deepscout_core.settings import Settings
from deepscout_persistence.knowledge import query_compiled_statements
from deepscout_persistence.models import ClaimRow, EvidenceRow
from deepscout_persistence.retrieval import (
    dense_search,
    lexical_search,
    list_chunks_for_run,
    load_chunks,
)
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.retrieval.bm25 import build_bm25_index
from deepscout_research.retrieval.embeddings import (
    EmbeddingSpec,
    build_embedding_client,
    embed_query,
)
from deepscout_research.retrieval.fusion import reciprocal_rank_fusion
from deepscout_research.retrieval.grader import grade_retrieval
from deepscout_research.retrieval.graph_search import graph_search_statements
from deepscout_research.retrieval.models import RetrievalQuery, RetrievedChunk
from deepscout_research.retrieval.planner import plan_retrieval_query
from deepscout_research.retrieval.rerank import rerank_candidates
from deepscout_research.retrieval.router import route_retrieval
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

    def retrieve_with_plan(
        self,
        *,
        query: str,
        run_id: uuid.UUID,
        task_id: uuid.UUID | None = None,
        source_ids: list[uuid.UUID] | None = None,
        document_token_estimate: int | None = None,
        fresher_than=None,
        research_mode: str | None = None,
    ) -> list[RetrievedChunk]:
        plan = plan_retrieval_query(
            query=query,
            run_id=run_id,
            settings=self._settings,
            task_id=task_id,
            source_ids=source_ids,
            document_token_estimate=document_token_estimate,
            fresher_than=fresher_than,
        )
        route = route_retrieval(
            plan,
            research_mode=research_mode or "standard",  # type: ignore[arg-type]
            router_enabled=self._settings.retrieval_router_enabled,
        )
        if route.skip_retrieval:
            return []
        return self.retrieve(
            RetrievalQuery(
                query=plan.semantic_query,
                run_id=run_id,
                task_id=task_id,
                source_ids=plan.source_ids,
                top_k=route.top_k,
                candidate_k=route.candidate_k,
                mode=route.mode,
                corpus=plan.corpus,
                fresher_than=plan.fresher_than,
                research_mode=research_mode or "standard",  # type: ignore[arg-type]
            )
        )

    def _search_once(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        run = self._store.get_run(request.run_id)
        if run is None:
            raise LookupError(f"ResearchRun {request.run_id} not found")

        plan = plan_retrieval_query(
            query=request.query,
            run_id=request.run_id,
            settings=self._settings,
            task_id=request.task_id,
            source_ids=request.source_ids,
            fresher_than=request.fresher_than,
        )
        plan = plan.model_copy(update={"corpus": request.corpus, "mode": request.mode})
        route = route_retrieval(
            plan,
            research_mode=request.research_mode,
            router_enabled=request.use_router and self._settings.retrieval_router_enabled,
        )
        if route.skip_retrieval:
            return []

        session = self._store._session
        source_ids = request.source_ids or None
        strategy = resolve_strategy(self._settings)
        mode = route.mode if route.mode in {"dense", "lexical", "hybrid"} else strategy_to_mode(strategy)

        dense_ranked: list[uuid.UUID] = []
        lexical_ranked: list[uuid.UUID] = []
        bm25_ranked: list[uuid.UUID] = []
        dense_scores: dict[uuid.UUID, float] = {}
        lexical_scores: dict[uuid.UUID, float] = {}
        bm25_scores: dict[uuid.UUID, float] = {}

        embed_future = None
        executor: ThreadPoolExecutor | None = None
        if route.use_dense and mode in {"dense", "hybrid"}:
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rag-embed")
            embed_future = executor.submit(embed_query, self._client, request.query)

        if route.use_fts and mode in {"lexical", "hybrid"}:
            lexical_hits = lexical_search(
                session,
                run_id=request.run_id,
                query=request.query,
                limit=request.candidate_k,
                source_ids=source_ids,
            )
            lexical_ranked = [item_id for item_id, _ in lexical_hits]
            lexical_scores = {item_id: score for item_id, score in lexical_hits}

        if route.use_bm25 and mode in {"lexical", "hybrid"}:
            chunk_rows = list_chunks_for_run(
                session, run_id=request.run_id, source_ids=source_ids
            )
            index = build_bm25_index(
                [
                    (
                        row.id,
                        row.context_text or row.text,
                    )
                    for row in chunk_rows
                ]
            )
            bm25_hits = index.search(request.query, limit=request.candidate_k)
            bm25_ranked = [item_id for item_id, _ in bm25_hits]
            bm25_scores = {item_id: score for item_id, score in bm25_hits}

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

        rank_lists = [lst for lst in (bm25_ranked, lexical_ranked, dense_ranked) if lst]
        fused = reciprocal_rank_fusion(rank_lists) if rank_lists else {}
        ordered_ids = sorted(fused, key=fused.get, reverse=True)

        compiled_candidates = self._compiled_candidates(
            request,
            route=route,
            limit=min(request.top_k, 8),
        )
        graph_candidates = self._graph_candidates(request, route=route, limit=min(request.top_k, 6))

        rows = load_chunks(session, ordered_ids)
        snapshots = {row.id: row for row in self._store.list_snapshots_for_run(request.run_id)}
        sources = {item.id: item for item in self._store.list_sources(request.run_id)}
        prefs = self._store.list_source_preferences(request.run_id)
        from deepscout_research.source_policy import is_excluded, is_pinned

        strategy_trace = route.reason
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
            source = sources.get(row.source_id)
            if source is not None and is_excluded(source.canonical_url, prefs):
                continue
            if (
                request.fresher_than
                and snapshot.retrieved_at
                and snapshot.retrieved_at < request.fresher_than
            ):
                continue
            dense_rank = dense_ranked.index(chunk_id) + 1 if chunk_id in dense_ranked else None
            lexical_rank = (
                lexical_ranked.index(chunk_id) + 1 if chunk_id in lexical_ranked else None
            )
            bm25_rank = bm25_ranked.index(chunk_id) + 1 if chunk_id in bm25_ranked else None
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
                    bm25_score=bm25_scores.get(chunk_id),
                    fused_score=fused.get(chunk_id, 0.0),
                    dense_rank=dense_rank,
                    lexical_rank=lexical_rank,
                    bm25_rank=bm25_rank,
                    retrieved_at=snapshot.retrieved_at,
                    section_title=row.section_title,
                    retrieval_reason="injection-flagged" if looks_like_injection(text) else "",
                    strategy_trace=strategy_trace,
                    provenance_kind="chunk",
                )
            )

        for item in candidates:
            source = sources.get(item.source_id)
            if source is not None and is_pinned(source.canonical_url, prefs):
                item.fused_score = item.fused_score + 0.15

        merged = compiled_candidates + graph_candidates + candidates
        if not request.apply_rerank:
            return merged[: request.top_k]
        reranked = self._apply_rerank(merged, query=request.query, limit=request.top_k)
        for item in reranked:
            if not item.strategy_trace:
                item.strategy_trace = strategy_trace
        return reranked

    def _apply_rerank(
        self, candidates: list[RetrievedChunk], *, query: str, limit: int
    ) -> list[RetrievedChunk]:
        if self._settings.reranker_mode == "cross_encoder":
            from deepscout_research.retrieval.cross_encoder import cross_encoder_rerank

            return cross_encoder_rerank(candidates, query=query, limit=limit)
        return rerank_candidates(candidates, query=query, limit=limit)

    def _compiled_candidates(
        self, request: RetrievalQuery, *, route, limit: int
    ) -> list[RetrievedChunk]:
        if not route.use_compiled or request.corpus == "raw":
            return []
        rows = query_compiled_statements(
            self._store._session,
            run_id=request.run_id,
            query=request.query,
            limit=limit,
        )
        out: list[RetrievedChunk] = []
        for row in rows:
            claim = (
                self._store._session.get(ClaimRow, row.claim_id) if row.claim_id else None
            )
            if claim is None or claim.source_id is None:
                continue
            snapshot_id = uuid.UUID(int=0)
            if row.evidence_id:
                evidence = self._store._session.get(EvidenceRow, row.evidence_id)
                if evidence is not None:
                    snapshot_id = evidence.snapshot_id
            text = sanitize_retrieved_text(row.statement_text)
            out.append(
                RetrievedChunk(
                    chunk_id=row.id,
                    snapshot_id=snapshot_id,
                    source_id=claim.source_id,
                    run_id=request.run_id,
                    text=text,
                    locator=f"wiki_statement:{row.id}",
                    ordinal=0,
                    start_offset=0,
                    end_offset=len(text),
                    fused_score=0.5,
                    retrieval_reason="compiled_knowledge",
                    strategy_trace=route.reason,
                    provenance_kind="compiled",
                    statement_id=row.id,
                    claim_id=row.claim_id,
                )
            )
        return out

    def _graph_candidates(self, request: RetrievalQuery, *, route, limit: int) -> list[RetrievedChunk]:
        if not route.use_graph:
            return []
        hits = graph_search_statements(
            self._store._session,
            run_id=request.run_id,
            query=request.query,
            limit=limit,
        )
        out: list[RetrievedChunk] = []
        for row, reason in hits:
            claim = (
                self._store._session.get(ClaimRow, row.claim_id) if row.claim_id else None
            )
            if claim is None or claim.source_id is None:
                continue
            text = sanitize_retrieved_text(row.statement_text)
            out.append(
                RetrievedChunk(
                    chunk_id=row.id,
                    snapshot_id=uuid.UUID(int=0),
                    source_id=claim.source_id,
                    run_id=request.run_id,
                    text=text,
                    locator=f"wiki_statement:{row.id}",
                    ordinal=0,
                    start_offset=0,
                    end_offset=len(text),
                    fused_score=0.45,
                    retrieval_reason=f"graph:{reason}",
                    strategy_trace=route.reason,
                    provenance_kind="compiled",
                    statement_id=row.id,
                    claim_id=row.claim_id,
                )
            )
        return out
