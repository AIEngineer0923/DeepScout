"""Retrieval quality benchmark — router, ablation, contextual, compiled, graph evaluation."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from deepscout_core.domain.enums import (
    KnowledgeProvenanceKind,
    KnowledgeRelationType,
    WikiPageType,
)
from deepscout_core.domain.schemas import (
    ClaimWrite,
    EvidenceWrite,
    ResearchRunCreate,
    SourceSnapshotWrite,
    SourceWrite,
)
from deepscout_core.settings import Settings
from deepscout_persistence import knowledge as knowledge_store
from deepscout_persistence.retrieval import dense_search, lexical_search, list_chunks_for_run
from deepscout_research.phases.compile_knowledge import compile_knowledge_for_run
from deepscout_research.retrieval.bm25 import build_bm25_index
from deepscout_research.retrieval.embeddings import embed_documents, embed_query
from deepscout_research.retrieval.fusion import reciprocal_rank_fusion
from deepscout_research.retrieval.graph_search import graph_search_statements
from deepscout_research.retrieval.models import RetrievalQuery
from deepscout_research.retrieval.planner import plan_retrieval_query
from deepscout_research.retrieval.rerank import rerank_candidates
from deepscout_research.retrieval.router import classify_intent, route_retrieval
from deepscout_research.retrieval.security import looks_like_injection
from deepscout_research.retrieval.service import RetrievalService

from deepscout_evaluation.retrieval_metrics import (
    hit_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

BENCHMARK_V2_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "retrieval_quality_benchmark_v2.json"
)


class AblationMode(StrEnum):
    BM25_ONLY = "bm25_only"
    FTS_ONLY = "fts_only"
    DENSE_ONLY = "dense_only"
    BM25_DENSE = "bm25_dense"
    FTS_DENSE = "fts_dense"
    BM25_FTS_DENSE = "bm25_fts_dense"
    FULL_RRF_RERANK = "full_rrf_rerank"


@dataclass
class RouterCaseResult:
    case_id: str
    query: str
    expected_intent: str
    actual_intent: str
    correct: bool
    corpus: str
    strategies: dict[str, bool]
    top_k: int
    candidate_k: int
    skip_retrieval: bool
    reason: str


@dataclass
class RetrievalQualityReport:
    version: str
    branch_head: str | None = None
    router: dict[str, Any] = field(default_factory=dict)
    ablation: dict[str, Any] = field(default_factory=dict)
    contextual: dict[str, Any] = field(default_factory=dict)
    compiled: dict[str, Any] = field(default_factory=dict)
    graph: dict[str, Any] = field(default_factory=dict)
    failure_cases: dict[str, Any] = field(default_factory=dict)
    cross_encoder: dict[str, Any] = field(default_factory=dict)
    latency: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def load_benchmark_v2(path: Path | None = None) -> dict[str, Any]:
    target = path or BENCHMARK_V2_PATH
    return json.loads(target.read_text())


def evaluate_router_cases(
    cases: list[dict[str, Any]],
    *,
    settings: Settings,
    research_mode: str = "standard",
) -> dict[str, Any]:
    results: list[RouterCaseResult] = []
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for case in cases:
        plan = plan_retrieval_query(
            query=case["query"],
            run_id=UUID(int=0),
            settings=settings,
            document_token_estimate=case.get("document_token_estimate", 5000),
        )
        actual_intent = classify_intent(plan).value
        route = route_retrieval(plan, research_mode=research_mode)  # type: ignore[arg-type]
        expected = case["expected_intent"]
        correct = actual_intent == expected
        confusion[expected][actual_intent] += 1
        results.append(
            RouterCaseResult(
                case_id=case["id"],
                query=case["query"],
                expected_intent=expected,
                actual_intent=actual_intent,
                correct=correct,
                corpus=plan.corpus,
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
                reason=route.reason,
            )
        )

    accuracy = sum(1 for row in results if row.correct) / len(results) if results else 0.0
    return {
        "accuracy": round(accuracy, 4),
        "total": len(results),
        "correct": sum(1 for row in results if row.correct),
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
        "cases": [
            {
                "id": row.case_id,
                "query": row.query,
                "expected_intent": row.expected_intent,
                "actual_intent": row.actual_intent,
                "correct": row.correct,
                "corpus": row.corpus,
                "strategies": row.strategies,
                "top_k": row.top_k,
                "candidate_k": row.candidate_k,
                "skip_retrieval": row.skip_retrieval,
                "reason": row.reason,
            }
            for row in results
        ],
    }


def _phrase_recall(texts: list[str], phrases: list[str]) -> float:
    if not phrases:
        return 1.0 if not texts else 0.0
    blob = " ".join(texts).lower()
    return sum(1 for phrase in phrases if phrase.lower() in blob) / len(phrases)


def score_retrieved_chunks(
    hits: list[Any],
    *,
    source_to_doc: dict[UUID, str],
    relevant_doc_ids: list[str],
    relevant_phrases: list[str],
    k: int = 5,
) -> dict[str, float]:
    retrieved_docs: list[str] = []
    for hit in hits[:k]:
        doc_id = source_to_doc.get(hit.source_id)
        if doc_id and doc_id not in retrieved_docs:
            retrieved_docs.append(doc_id)
    relevant = set(relevant_doc_ids)
    if not relevant:
        found = 0
        first = None
        gains = [0.0] * min(len(hits), k)
        hit_flag = 1.0 if not hits else 0.0
        return {
            "hit_at_1": hit_flag if k >= 1 else 0.0,
            "hit_at_3": hit_flag if k >= 3 else 0.0,
            "hit_at_5": hit_flag if k >= 5 else 0.0,
            "recall_at_k": 1.0 if not hits else 0.0,
            "precision_at_k": 1.0 if not hits else 0.0,
            "mrr": 1.0 if not hits else 0.0,
            "ndcg_at_k": 1.0 if not hits else 0.0,
            "phrase_recall": _phrase_recall([h.text for h in hits[:k]], relevant_phrases),
            "relevant_found": float(found),
            "first_relevant_rank": float(first or 0),
        }

    found_docs = [doc for doc in retrieved_docs if doc in relevant]
    found = len(found_docs)
    first = None
    gains: list[float] = []
    for idx, hit in enumerate(hits[:k], start=1):
        doc_id = source_to_doc.get(hit.source_id)
        gain = 1.0 if doc_id in relevant else 0.0
        gains.append(gain)
        if gain > 0 and first is None:
            first = idx
    metrics = {
        "hit_at_k": hit_at_k(relevant_found=found, k=k),
        "recall_at_k": recall_at_k(relevant_found=found, total_relevant=len(relevant), k=k),
        "precision_at_k": precision_at_k(relevant_found=found, returned=len(hits[:k]), k=k),
        "mrr": mrr(first_relevant_rank=first),
        "ndcg_at_k": ndcg_at_k(gains=gains, k=k),
        "phrase_recall": _phrase_recall([h.text for h in hits[:k]], relevant_phrases),
        "relevant_found": float(found),
        "first_relevant_rank": float(first or 0),
    }
    for kk in (1, 3, 5):
        if kk <= k:
            sub_found = sum(
                1
                for hit in hits[:kk]
                if source_to_doc.get(hit.source_id) in relevant
            )
            metrics[f"hit_at_{kk}"] = hit_at_k(relevant_found=sub_found, k=kk)
    return metrics


def _mean_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    skip = {"relevant_found", "first_relevant_rank"}
    keys = [
        key
        for key, value in rows[0].items()
        if key not in skip and isinstance(value, (int, float))
    ]
    out: dict[str, float] = {}
    for key in keys:
        values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
        if values:
            out[key] = round(sum(values) / len(values), 4)
    return out


def seed_benchmark_corpus(
    store,
    settings: Settings,
    documents: list[dict[str, Any]],
    *,
    goal: str = "retrieval-quality-benchmark",
) -> tuple[Any, dict[str, UUID], dict[UUID, str]]:
    run = store.create_run(
        ResearchRunCreate(goal=goal, budget=settings.default_research_budget()),
        settings,
    )
    doc_to_source: dict[str, UUID] = {}
    for doc in documents:
        source, _ = store.add_source(
            run.id,
            SourceWrite(canonical_url=f"https://benchmark.local/{doc['id']}", title=doc["title"]),
        )
        store.add_snapshot(source.id, SourceSnapshotWrite(content=doc["text"]))
        doc_to_source[doc["id"]] = source.id
    store.commit()
    source_to_doc = {source_id: doc_id for doc_id, source_id in doc_to_source.items()}
    return run, doc_to_source, source_to_doc


def run_ablation_retrieval(
    service: RetrievalService,
    *,
    session,
    run_id: UUID,
    query: str,
    mode: AblationMode,
    top_k: int = 5,
    candidate_k: int = 20,
    spec=None,
    client=None,
) -> tuple[list[Any], float]:
    """Run a single retriever configuration without changing production defaults."""
    t0 = time.perf_counter()
    source_ids = None

    if mode == AblationMode.FULL_RRF_RERANK:
        hits = service.retrieve(
            RetrievalQuery(
                query=query,
                run_id=run_id,
                top_k=top_k,
                candidate_k=candidate_k,
                mode="hybrid",
                apply_rerank=True,
            )
        )
        return hits, time.perf_counter() - t0

    bm25_ranked: list[UUID] = []
    lexical_ranked: list[UUID] = []
    dense_ranked: list[UUID] = []

    if mode in {
        AblationMode.BM25_ONLY,
        AblationMode.BM25_DENSE,
        AblationMode.BM25_FTS_DENSE,
    }:
        chunk_rows = list_chunks_for_run(session, run_id=run_id, source_ids=source_ids)
        index = build_bm25_index(
            [(row.id, row.context_text or row.text) for row in chunk_rows]
        )
        bm25_ranked = [item_id for item_id, _ in index.search(query, limit=candidate_k)]

    if mode in {
        AblationMode.FTS_ONLY,
        AblationMode.FTS_DENSE,
        AblationMode.BM25_FTS_DENSE,
    }:
        lexical_hits = lexical_search(
            session, run_id=run_id, query=query, limit=candidate_k, source_ids=source_ids
        )
        lexical_ranked = [item_id for item_id, _ in lexical_hits]

    if mode in {
        AblationMode.DENSE_ONLY,
        AblationMode.BM25_DENSE,
        AblationMode.FTS_DENSE,
        AblationMode.BM25_FTS_DENSE,
    }:
        if client is None or spec is None:
            raise ValueError("dense ablation requires embedding client and spec")
        vector = embed_query(client, query)
        dense_hits = dense_search(
            session,
            run_id=run_id,
            query_vector=vector,
            provider=spec.provider,
            model=spec.model,
            dimensions=spec.dimensions,
            config_version=spec.config_version,
            limit=candidate_k,
            source_ids=source_ids,
        )
        dense_ranked = [item_id for item_id, _ in dense_hits]

    rank_lists = [lst for lst in (bm25_ranked, lexical_ranked, dense_ranked) if lst]
    fused = reciprocal_rank_fusion(rank_lists) if rank_lists else {}
    ordered_ids = sorted(fused, key=fused.get, reverse=True)[:candidate_k]

    full_hits = service.retrieve(
        RetrievalQuery(
            query=query,
            run_id=run_id,
            top_k=top_k,
            candidate_k=candidate_k,
            mode="hybrid",
            apply_rerank=False,
        )
    )
    by_chunk = {hit.chunk_id: hit for hit in full_hits}
    hits = [by_chunk[cid] for cid in ordered_ids if cid in by_chunk][:top_k]

    if mode == AblationMode.BM25_FTS_DENSE:
        hits = rerank_candidates(hits, query=query, limit=top_k)

    return hits, time.perf_counter() - t0


def evaluate_ablation_suite(
    service: RetrievalService,
    *,
    session,
    run_id: UUID,
    cases: list[dict[str, Any]],
    source_to_doc: dict[UUID, str],
    spec=None,
    client=None,
    top_k: int = 5,
    candidate_k: int = 20,
) -> dict[str, Any]:
    modes = list(AblationMode)
    out: dict[str, Any] = {}
    for mode in modes:
        per_query: list[dict[str, Any]] = []
        latencies: list[float] = []
        for case in cases:
            hits, latency = run_ablation_retrieval(
                service,
                session=session,
                run_id=run_id,
                query=case["query"],
                mode=mode,
                top_k=top_k,
                candidate_k=candidate_k,
                spec=spec,
                client=client,
            )
            latencies.append(latency)
            metrics = score_retrieved_chunks(
                hits,
                source_to_doc=source_to_doc,
                relevant_doc_ids=case.get("relevant_doc_ids", []),
                relevant_phrases=case.get("relevant_phrases", []),
                k=top_k,
            )
            per_query.append({"id": case["id"], "intent": case.get("intent"), **metrics})
        out[mode.value] = {
            "aggregate": _mean_metrics(per_query),
            "mean_latency_s": round(sum(latencies) / len(latencies), 4) if latencies else 0.0,
            "per_query": per_query,
        }
    return out


def compare_contextual_embeddings(
    service: RetrievalService,
    *,
    session,
    run_id: UUID,
    cases: list[dict[str, Any]],
    source_to_doc: dict[UUID, str],
    client,
    spec,
    top_k: int = 5,
    candidate_k: int = 20,
) -> dict[str, Any]:
    """Compare dense retrieval using raw chunk text vs contextual embedding text."""
    per_query: list[dict[str, Any]] = []
    for case in cases:
        chunk_rows = list_chunks_for_run(session, run_id=run_id)
        if not chunk_rows:
            continue
        raw_vectors = embed_documents(client, [row.text for row in chunk_rows])
        ctx_vectors = embed_documents(
            client, [row.context_text or row.text for row in chunk_rows]
        )
        query_vec = embed_query(client, case["query"])

        def _rank_rows(rows: list, vectors: list[list[float]], qvec: list[float]) -> list[UUID]:
            scored = []
            for row, vec in zip(rows, vectors, strict=True):
                dot = sum(a * b for a, b in zip(qvec, vec, strict=True))
                scored.append((row.id, dot))
            scored.sort(key=lambda item: item[1], reverse=True)
            return [cid for cid, _ in scored[:candidate_k]]

        raw_ids = _rank_rows(chunk_rows, raw_vectors, query_vec)
        ctx_ids = _rank_rows(chunk_rows, ctx_vectors, query_vec)
        full_hits = service.retrieve(
            RetrievalQuery(
                query=case["query"],
                run_id=run_id,
                top_k=top_k,
                candidate_k=candidate_k,
                apply_rerank=False,
            )
        )
        by_chunk = {hit.chunk_id: hit for hit in full_hits}
        case_doc_ids = case.get("relevant_doc_ids", [])
        case_phrases = case.get("relevant_phrases", [])

        raw_hits = [by_chunk[cid] for cid in raw_ids if cid in by_chunk][:top_k]
        raw_m = score_retrieved_chunks(
            raw_hits,
            source_to_doc=source_to_doc,
            relevant_doc_ids=case_doc_ids,
            relevant_phrases=case_phrases,
            k=top_k,
        )
        ctx_hits = [by_chunk[cid] for cid in ctx_ids if cid in by_chunk][:top_k]
        ctx_m = score_retrieved_chunks(
            ctx_hits,
            source_to_doc=source_to_doc,
            relevant_doc_ids=case_doc_ids,
            relevant_phrases=case_phrases,
            k=top_k,
        )
        per_query.append(
            {
                "id": case["id"],
                "raw": raw_m,
                "contextual": ctx_m,
                "delta_hit_at_3": round(ctx_m.get("hit_at_3", 0) - raw_m.get("hit_at_3", 0), 4),
                "delta_mrr": round(ctx_m.get("mrr", 0) - raw_m.get("mrr", 0), 4),
                "contextual_better": ctx_m.get("mrr", 0) > raw_m.get("mrr", 0),
            }
        )
    improved = sum(1 for row in per_query if row["contextual_better"])
    return {
        "per_query": per_query,
        "contextual_better_count": improved,
        "total": len(per_query),
        "note": "Dot-product on freshly embedded vectors; production uses stored pgvector index.",
    }


def seed_compiled_fixture(
    store,
    settings: Settings,
    documents: list[dict[str, Any]],
    fixture: dict[str, Any],
) -> tuple[Any, dict[str, UUID]]:
    run, doc_to_source, _ = seed_benchmark_corpus(store, settings, documents)
    snapshots = store.list_snapshots_for_run(run.id)
    snap_by_source = {snap.source_id: snap for snap in snapshots}
    for claim_spec in fixture["claims"]:
        source_id = doc_to_source[claim_spec["doc_id"]]
        snapshot = snap_by_source[source_id]
        claim = store.add_claim(
            run.id,
            ClaimWrite(statement=claim_spec["statement"], source_id=source_id),
        )
        store.attach_evidence(
            claim.id,
            EvidenceWrite(
                snapshot_id=snapshot.id,
                quote=claim_spec["quote"],
                locator="offset:0-80",
                support_strength=1.0,
                confidence=1.0,
            ),
        )
    store.commit()
    compile_knowledge_for_run(store, run.id)
    store.commit()
    return run, doc_to_source


def evaluate_compiled_retrieval(
    service: RetrievalService,
    *,
    run_id: UUID,
    fixture: dict[str, Any],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in fixture["queries"]:
        hits = service.retrieve(
            RetrievalQuery(
                query=case["query"],
                run_id=run_id,
                top_k=5,
                candidate_k=15,
                corpus="compiled" if "learned" in case["query"] else "raw",
            )
        )
        compiled_hits = [h for h in hits if h.provenance_kind == "compiled"]
        phrase_hit = _phrase_recall([h.text for h in hits], case.get("relevant_phrases", []))
        results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "compiled_hit_count": len(compiled_hits),
                "expect_compiled_hit": case.get("expect_compiled_hit"),
                "phrase_recall": phrase_hit,
                "strategy_traces": list({h.strategy_trace for h in hits if h.strategy_trace}),
                "passed": (
                    len(compiled_hits) > 0
                    if case.get("expect_compiled_hit")
                    else phrase_hit > 0
                ),
            }
        )
    return {"cases": results, "passed": sum(1 for row in results if row["passed"])}


def seed_graph_fixture(
    store,
    db_session,
    settings: Settings,
    fixture: dict[str, Any],
) -> UUID:
    run = store.create_run(
        ResearchRunCreate(
            goal="graph-quality-benchmark",
            budget=settings.default_research_budget(),
        ),
        settings,
    )
    page = knowledge_store.create_page(
        db_session,
        run_id=run.id,
        slug="graph-topic",
        title="Graph Topic",
        page_type=WikiPageType.TOPIC,
    )
    stmt_ids: dict[str, UUID] = {}
    for item in fixture["statements"]:
        row = knowledge_store.add_statement(
            db_session,
            run_id=run.id,
            page_id=page.id,
            statement_text=item["text"],
            claim_id=None,
            evidence_id=None,
        )
        stmt_ids[item["key"]] = row.id
    for rel in fixture["relations"]:
        knowledge_store.add_relation(
            db_session,
            run_id=run.id,
            from_statement_id=stmt_ids[rel["from"]],
            to_statement_id=stmt_ids[rel["to"]],
            relation_type=KnowledgeRelationType.RELATED_TO,
            provenance_kind=KnowledgeProvenanceKind.DETERMINISTIC,
        )
    store.commit()
    return run.id


def evaluate_graph_retrieval(
    db_session,
    *,
    run_id: UUID,
    fixture: dict[str, Any],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in fixture["queries"]:
        hits = graph_search_statements(db_session, run_id=run_id, query=case["query"], limit=5)
        results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "hit_count": len(hits),
                "reasons": [reason for _, reason in hits],
                "expect_graph_hit": case.get("expect_graph_hit", False),
                "passed": (len(hits) > 0) == bool(case.get("expect_graph_hit")),
            }
        )
    return {"cases": results, "passed": sum(1 for row in results if row["passed"])}


def evaluate_failure_cases(
    service: RetrievalService,
    *,
    run_id: UUID,
    cases: list[dict[str, Any]],
    source_to_doc: dict[UUID, str],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in cases:
        hits = service.retrieve(
            RetrievalQuery(query=case["query"], run_id=run_id, top_k=5, candidate_k=15)
        )
        metrics = score_retrieved_chunks(
            hits,
            source_to_doc=source_to_doc,
            relevant_doc_ids=case.get("relevant_doc_ids", []),
            relevant_phrases=[],
            k=3,
        )
        injection_flag = any(looks_like_injection(h.text) for h in hits)
        query_injection = looks_like_injection(case["query"])
        row = {
            "id": case["id"],
            "query": case["query"],
            "hit_at_3": metrics.get("hit_at_3", metrics.get("hit_at_k", 0)),
            "injection_flag_in_results": injection_flag,
            "injection_flag_in_query": query_injection,
            "passed": True,
        }
        if case.get("expect_hit_at_3") is not None:
            row["passed"] = row["hit_at_3"] <= case["expect_hit_at_3"]
        if case.get("expect_injection_query"):
            row["passed"] = query_injection and not any(
                "api key" in h.text.lower() for h in hits
            )
        results.append(row)
    return {"cases": results, "passed": sum(1 for row in results if row["passed"])}
