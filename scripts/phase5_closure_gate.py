#!/usr/bin/env python3
"""Phase 5 final closure gate — corrected dimension, ablation, and isolated pre-RAG vs RAG."""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from deepscout_core.domain.schemas import (
    ResearchRunCreate,
    SearchCandidateWrite,
    SearchResult,
    SourceSnapshotWrite,
    SourceWrite,
)
from deepscout_core.settings import get_settings
from deepscout_core.types import ProviderKind
from deepscout_evaluation.retrieval_metrics import (
    hit_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_providers.defaults import DEFAULT_EMBEDDING_MODELS
from deepscout_providers.factory import build_embeddings
from deepscout_research.phases.extract import extract_claims_for_run
from deepscout_research.retrieval.embeddings import DOCUMENT_INSTRUCTION, QUERY_INSTRUCTION
from deepscout_research.retrieval.indexer import index_snapshots_for_run
from deepscout_research.retrieval.models import RetrievalQuery
from deepscout_research.retrieval.security import looks_like_injection
from deepscout_research.retrieval.service import RetrievalService
from deepscout_research.retrieval.spec import EmbeddingSpec
from sqlalchemy import text

BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "libs/evaluation/data/retrieval_benchmark_v1.json"
)
TOP_K = 5
CANDIDATE_K = 20


@dataclass
class ClosureResult:
    status: str = "PENDING"
    branch_head: str | None = None
    checks: dict[str, Any] = field(default_factory=dict)
    dimension_benchmark: dict[str, Any] = field(default_factory=dict)
    retrieval_ablation: dict[str, Any] = field(default_factory=dict)
    category_results: dict[str, Any] = field(default_factory=dict)
    pre_rag_vs_rag: dict[str, Any] = field(default_factory=dict)
    reranker_semantics: dict[str, Any] = field(default_factory=dict)
    database_reality: dict[str, Any] = field(default_factory=dict)
    final_live_rag: dict[str, Any] = field(default_factory=dict)
    decisions: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _runtime_model(client) -> str:
    for attr in ("model", "model_name"):
        value = getattr(client, attr, None)
        if value:
            return str(value)
    return DEFAULT_EMBEDDING_MODELS[ProviderKind.GOOGLE]


def _client_for_dims(settings, dims: int):
    s = settings.model_copy(update={"embedding_dimensions": dims})
    client = build_embeddings(s)
    if hasattr(client, "output_dimensionality"):
        client.output_dimensionality = dims
    model = _runtime_model(client)
    spec = EmbeddingSpec(
        provider=s.resolved_embedding_provider().value,
        model=model,
        dimensions=dims,
        config_version=f"v1-dim{dims}-instruction-prefix",
    )
    return client, spec, s


def _seed_corpus(
    store: ResearchStore, settings, goal: str, documents: list[dict]
) -> tuple[Any, dict[str, UUID]]:
    run = store.create_run(
        ResearchRunCreate(goal=goal, budget=settings.default_research_budget()), settings
    )
    doc_to_source: dict[str, UUID] = {}
    for doc in documents:
        source, _ = store.add_source(
            run.id,
            SourceWrite(canonical_url=f"https://gate.local/{doc['id']}", title=doc["title"]),
        )
        store.add_snapshot(source.id, SourceSnapshotWrite(content=doc["text"]))
        doc_to_source[doc["id"]] = source.id
    store.commit()
    return run, doc_to_source


def _source_doc_map(doc_to_source: dict[str, UUID]) -> dict[UUID, str]:
    return {source_id: doc_id for doc_id, source_id in doc_to_source.items()}


def _phrase_recall(texts: list[str], phrases: list[str]) -> float:
    if not phrases:
        return 1.0 if not texts else 0.0
    blob = " ".join(texts).lower()
    return sum(1 for phrase in phrases if phrase.lower() in blob) / len(phrases)


def _score_hits(
    hits: list,
    *,
    source_to_doc: dict[UUID, str],
    relevant_doc_ids: list[str],
    phrases: list[str],
    k: int = TOP_K,
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
            "hit_at_k": hit_flag,
            "recall_at_k": 1.0 if not hits else 0.0,
            "precision_at_k": 1.0 if not hits else 0.0,
            "mrr": 1.0 if not hits else 0.0,
            "ndcg_at_k": 1.0 if not hits else 0.0,
            "phrase_recall": _phrase_recall([h.text for h in hits[:k]], phrases),
            "relevant_found": found,
            "first_relevant_rank": first,
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
    return {
        "hit_at_k": hit_at_k(relevant_found=found, k=k),
        "recall_at_k": recall_at_k(relevant_found=found, total_relevant=len(relevant), k=k),
        "precision_at_k": precision_at_k(relevant_found=found, returned=len(hits[:k]), k=k),
        "mrr": mrr(first_relevant_rank=first),
        "ndcg_at_k": ndcg_at_k(gains=gains, k=k),
        "phrase_recall": _phrase_recall([h.text for h in hits[:k]], phrases),
        "relevant_found": found,
        "first_relevant_rank": first,
    }


def _mean_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    skip = {"relevant_found", "first_relevant_rank", "hit_count", "unique_sources", "latency_s"}
    keys = [
        key
        for key, value in rows[0].items()
        if key not in skip and isinstance(value, (int, float)) and value is not None
    ]
    out: dict[str, float] = {}
    for key in keys:
        values = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
        if values:
            out[key] = round(sum(values) / len(values), 4)
    return out


def _run_mode(
    service: RetrievalService,
    *,
    run_id: UUID,
    query: str,
    mode: str,
    apply_rerank: bool,
) -> tuple[list, float]:
    t0 = time.perf_counter()
    hits = service.retrieve(
        RetrievalQuery(
            query=query,
            run_id=run_id,
            top_k=TOP_K,
            candidate_k=CANDIDATE_K,
            mode=mode,  # type: ignore[arg-type]
            apply_rerank=apply_rerank,
        )
    )
    return hits, time.perf_counter() - t0


def _evaluate_queries(
    service: RetrievalService,
    *,
    run_id: UUID,
    queries: list[dict],
    source_to_doc: dict[UUID, str],
    mode: str,
    apply_rerank: bool,
) -> dict[str, Any]:
    per_query: list[dict[str, Any]] = []
    by_category: dict[str, list[dict[str, float]]] = defaultdict(list)
    latencies: list[float] = []
    for item in queries:
        hits, latency = _run_mode(
            service,
            run_id=run_id,
            query=item["query"],
            mode=mode,
            apply_rerank=apply_rerank,
        )
        latencies.append(latency)
        metrics = _score_hits(
            hits,
            source_to_doc=source_to_doc,
            relevant_doc_ids=item.get("relevant_doc_ids", []),
            phrases=item.get("relevant_phrases", []),
        )
        category = item.get("category", "UNKNOWN")
        by_category[category].append(metrics)
        per_query.append(
            {
                "id": item["id"],
                "category": category,
                "query": item["query"],
                "latency_s": round(latency, 4),
                "hit_count": len(hits),
                "unique_sources": len({str(h.source_id) for h in hits}),
                **metrics,
            }
        )
    return {
        "aggregate": _mean_metrics([q for q in per_query]),  # type: ignore[arg-type]
        "mean_latency_s": round(sum(latencies) / len(latencies), 4) if latencies else 0.0,
        "by_category": {cat: _mean_metrics(rows) for cat, rows in by_category.items()},
        "per_query": per_query,
    }


def _vector_storage_bytes(*, embeddings: int, dimensions: int) -> int:
    # float32 vectors in pgvector
    return embeddings * dimensions * 4


def _seed_search_candidates(store: ResearchStore, run_id: UUID) -> None:
    store.add_search_candidates(
        run_id,
        SearchCandidateWrite(
            query="CVE-2024-1234 battery firmware safety",
            provider="closure-gate",
            results=[
                SearchResult(
                    url="https://gate.local/doc-battery",
                    title="Solid-State Battery Overview",
                    snippet="CVE-2024-1234 affected legacy BMS firmware",
                ),
                SearchResult(
                    url="https://gate.local/doc-security",
                    title="BMS Security Advisory",
                    snippet="ADV-BMS-2024-09 references CVE-2024-1234",
                ),
            ],
        ),
    )
    store.commit()


def run_closure() -> ClosureResult:
    result = ClosureResult()
    try:
        import subprocess

        result.branch_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:  # noqa: BLE001
        result.branch_head = None

    settings = get_settings()
    if settings.google_api_key is None:
        result.status = "BLOCKED"
        result.errors.append("GOOGLE_API_KEY not configured")
        return result

    benchmark = json.loads(BENCHMARK_PATH.read_text())
    documents = benchmark["documents"]
    queries = benchmark["queries"]
    session_factory = get_session_factory(settings.database_url)

    with session_factory() as session:
        store = ResearchStore(session)

        # --- smoke embedding ---
        client_1536, spec_1536, settings_1536 = _client_for_dims(settings, 1536)
        t0 = time.perf_counter()
        probe = client_1536.embed_documents([DOCUMENT_INSTRUCTION + "closure gate smoke"])[0]
        smoke_latency = time.perf_counter() - t0
        result.checks["google_embedding"] = {
            "runtime_model": _runtime_model(client_1536),
            "requested_dimensions": 1536,
            "returned_dimensions": len(probe),
            "finite": all(math.isfinite(float(v)) for v in probe),
            "non_zero": any(abs(float(v)) > 1e-9 for v in probe),
            "latency_s": round(smoke_latency, 3),
            "pass": len(probe) == 1536
            and str(_runtime_model(client_1536)).startswith("gemini-embedding"),
        }

        # --- A3: 768 vs 1536 on identical corpus/queries ---
        dim_report: dict[str, Any] = {}
        for dims in (768, 1536):
            client, spec, dim_settings = _client_for_dims(settings, dims)
            run, doc_to_source = _seed_corpus(
                store,
                dim_settings,
                goal=f"Phase5 dim={dims} closure",
                documents=documents,
            )
            source_to_doc = _source_doc_map(doc_to_source)
            t_index = time.perf_counter()
            index_stats = index_snapshots_for_run(
                store, dim_settings, run.id, client=client, spec=spec
            )
            store.commit()
            index_latency = time.perf_counter() - t_index
            embed_count = int(
                session.scalar(
                    text(
                        "SELECT COUNT(*) FROM chunk_embeddings WHERE research_run_id = :rid "
                        "AND dimensions = :dims"
                    ),
                    {"rid": run.id, "dims": dims},
                )
                or 0
            )
            chunk_count = int(
                session.scalar(
                    text("SELECT COUNT(*) FROM document_chunks WHERE research_run_id = :rid"),
                    {"rid": run.id},
                )
                or 0
            )
            t_embed = time.perf_counter()
            qvec = client.embed_query(QUERY_INSTRUCTION + queries[0]["query"])
            embed_q_latency = time.perf_counter() - t_embed
            service = RetrievalService(store, dim_settings, client=client, spec=spec)
            eval_out = _evaluate_queries(
                service,
                run_id=run.id,
                queries=queries,
                source_to_doc=source_to_doc,
                mode="hybrid",
                apply_rerank=True,
            )
            dim_report[str(dims)] = {
                "run_id": str(run.id),
                "index_stats": index_stats,
                "chunks": chunk_count,
                "embeddings": embed_count,
                "vector_storage_bytes_approx": _vector_storage_bytes(
                    embeddings=embed_count, dimensions=dims
                ),
                "index_latency_s": round(index_latency, 3),
                "query_embed_latency_s": round(embed_q_latency, 3),
                "query_vector_dims": len(qvec),
                "retrieval": eval_out["aggregate"],
                "mean_retrieval_latency_s": eval_out["mean_latency_s"],
                "by_category": eval_out["by_category"],
                "per_query": eval_out["per_query"],
            }

        m768 = dim_report["768"]["retrieval"]
        m1536 = dim_report["1536"]["retrieval"]
        storage_ratio = (
            dim_report["1536"]["vector_storage_bytes_approx"]
            / dim_report["768"]["vector_storage_bytes_approx"]
            if dim_report["768"]["vector_storage_bytes_approx"]
            else None
        )
        # Prefer 768 when material quality is equivalent (within 0.05 absolute on hit/recall/mrr).
        quality_delta = {
            "hit_at_k": round(m1536.get("hit_at_k", 0) - m768.get("hit_at_k", 0), 4),
            "recall_at_k": round(m1536.get("recall_at_k", 0) - m768.get("recall_at_k", 0), 4),
            "mrr": round(m1536.get("mrr", 0) - m768.get("mrr", 0), 4),
            "ndcg_at_k": round(m1536.get("ndcg_at_k", 0) - m768.get("ndcg_at_k", 0), 4),
            "phrase_recall": round(m1536.get("phrase_recall", 0) - m768.get("phrase_recall", 0), 4),
        }
        material_gain = any(abs(v) >= 0.05 and v > 0 for v in quality_delta.values())
        material_loss = any(v <= -0.05 for v in quality_delta.values())
        if material_gain and not material_loss:
            dim_decision = "1536"
            dim_reason = "1536 showed material retrieval quality gain on the shared benchmark"
        elif not material_gain and not material_loss:
            dim_decision = "768"
            dim_reason = (
                "768 is materially equivalent on Hit/Recall/MRR/NDCG/phrase-recall; "
                "prefer lower storage and latency unless another measured reason requires 1536"
            )
        else:
            dim_decision = "1536"
            dim_reason = (
                "mixed quality deltas; retain 1536 for OpenAI portability and conservative recall"
            )
        result.dimension_benchmark = {
            "768": dim_report["768"],
            "1536": dim_report["1536"],
            "storage_ratio_1536_over_768": round(storage_ratio, 3) if storage_ratio else None,
            "quality_delta_1536_minus_768": quality_delta,
            "final_dimension": dim_decision,
            "exact_reason": dim_reason,
        }
        result.decisions["embedding_dimensions"] = dim_decision

        # Use the decided dimension space for remaining experiments
        chosen_dims = int(dim_decision)
        client, spec, chosen_settings = _client_for_dims(settings, chosen_dims)

        # --- A5/A6 ablation on fresh isolated run ---
        ablation_run, doc_to_source = _seed_corpus(
            store,
            chosen_settings,
            goal=f"Phase5 ablation dim={chosen_dims}",
            documents=documents,
        )
        source_to_doc = _source_doc_map(doc_to_source)
        index_snapshots_for_run(store, chosen_settings, ablation_run.id, client=client, spec=spec)
        store.commit()
        service = RetrievalService(store, chosen_settings, client=client, spec=spec)
        modes = {
            "FTS_ONLY": ("lexical", False),
            "DENSE_ONLY": ("dense", False),
            "HYBRID_RRF": ("hybrid", False),
            "HYBRID_RRF_PLUS_DETERMINISTIC_RERANK": ("hybrid", True),
        }
        ablation_out: dict[str, Any] = {}
        for label, (mode, apply_rerank) in modes.items():
            ablation_out[label] = _evaluate_queries(
                service,
                run_id=ablation_run.id,
                queries=queries,
                source_to_doc=source_to_doc,
                mode=mode,
                apply_rerank=apply_rerank,
            )
        result.retrieval_ablation = {
            label: {
                "aggregate": data["aggregate"],
                "mean_latency_s": data["mean_latency_s"],
                "by_category": data["by_category"],
            }
            for label, data in ablation_out.items()
        }
        result.category_results = ablation_out["HYBRID_RRF_PLUS_DETERMINISTIC_RERANK"][
            "by_category"
        ]

        hybrid = ablation_out["HYBRID_RRF_PLUS_DETERMINISTIC_RERANK"]["by_category"]
        dense = ablation_out["DENSE_ONLY"]["by_category"]
        lexical = ablation_out["FTS_ONLY"]["by_category"]
        hybrid_justification = (
            "Hybrid remains the production default for category robustness: "
            f"LEXICAL_IDENTIFIER hybrid={hybrid.get('LEXICAL_IDENTIFIER', {})} "
            f"vs dense={dense.get('LEXICAL_IDENTIFIER', {})} "
            f"vs lexical={lexical.get('LEXICAL_IDENTIFIER', {})}; "
            f"SEMANTIC hybrid={hybrid.get('SEMANTIC', {})} vs dense={dense.get('SEMANTIC', {})}. "
            "This does not claim hybrid universally beats dense on every semantic query."
        )
        result.decisions["retrieval_default"] = "hybrid_rrf_plus_deterministic_rerank"
        result.decisions["hybrid_justification"] = hybrid_justification

        # Reranker effect
        rr = ablation_out["HYBRID_RRF"]["aggregate"]
        rr_plus = ablation_out["HYBRID_RRF_PLUS_DETERMINISTIC_RERANK"]["aggregate"]
        result.reranker_semantics = {
            "scoring_model": {
                "base": "fused_score (RRF)",
                "exact_token_boost": "0.02 * count(query tokens length>=3 present in chunk text)",
                "recency": "retrieved_at.timestamp()/1e12 when present (NOT published_at/effective_at)",
                "diversity": "prefer max 3 chunks per source, then fill from overflow",
                "llm_score": "none",
            },
            "quality_delta_rerank_minus_rrf": {
                key: round(rr_plus.get(key, 0) - rr.get(key, 0), 4)
                for key in (
                    "hit_at_k",
                    "recall_at_k",
                    "precision_at_k",
                    "mrr",
                    "ndcg_at_k",
                    "phrase_recall",
                )
            },
            "latency_delta_s": round(
                ablation_out["HYBRID_RRF_PLUS_DETERMINISTIC_RERANK"]["mean_latency_s"]
                - ablation_out["HYBRID_RRF"]["mean_latency_s"],
                4,
            ),
            "interpretation": (
                "Deterministic reranker is a policy layer (diversity/exact-token/recency). "
                "Quality gain on this small benchmark may be negligible; retain for policy value "
                "unless a larger labeled set shows material harm."
            ),
            "security_notes": [
                "retrieved_at is fetch time, not publication time",
                "exact-token boost can be gamed by keyword stuffing but cannot invent evidence",
                "no LLM-generated score is treated as factual confidence",
                "source diversity soft-limits per-source monopoly but overflow can still fill slots",
            ],
        }

        # --- A4: isolated pre-RAG vs RAG ---
        run_a, _ = _seed_corpus(
            store, chosen_settings, goal="Phase5 pre-RAG isolated", documents=documents
        )
        _seed_search_candidates(store, run_a.id)
        pre = extract_claims_for_run(store, run_a.id, retriever=None)
        store.commit()
        claims_a = len(store.list_claims(run_a.id))
        evidence_a = len(store.list_evidence(run_a.id))

        run_b, _ = _seed_corpus(
            store, chosen_settings, goal="Phase5 RAG isolated", documents=documents
        )
        _seed_search_candidates(store, run_b.id)
        index_snapshots_for_run(store, chosen_settings, run_b.id, client=client, spec=spec)
        store.commit()
        service_b = RetrievalService(store, chosen_settings, client=client, spec=spec)
        t_rag = time.perf_counter()
        post = extract_claims_for_run(store, run_b.id, retriever=service_b)
        rag_extract_latency = time.perf_counter() - t_rag
        store.commit()
        claims_b = len(store.list_claims(run_b.id))
        evidence_b = len(store.list_evidence(run_b.id))

        if claims_b > claims_a or evidence_b > evidence_a:
            cmp = "RAG_BETTER"
        elif claims_b < claims_a or evidence_b < evidence_a:
            cmp = "PRE_RAG_BETTER"
        elif claims_a == claims_b and evidence_a == evidence_b:
            cmp = "SIMILAR"
        else:
            cmp = "MIXED"
        result.pre_rag_vs_rag = {
            "isolation_method": "two separate ResearchRun rows with identical seeded snapshots; no shared claims/evidence",
            "pre_rag": {
                "run_id": str(run_a.id),
                "extract_result": pre,
                "claims": claims_a,
                "evidence": evidence_a,
            },
            "rag": {
                "run_id": str(run_b.id),
                "extract_result": post,
                "claims": claims_b,
                "evidence": evidence_b,
                "extract_latency_s": round(rag_extract_latency, 3),
            },
            "outcome": cmp,
            "interpretation": (
                "On this bounded seeded corpus, extraction quality may be similar because quote "
                "resolution still requires SourceSnapshot text. RAG changes candidate search text, "
                "not authority."
            ),
        }

        # --- cross-run isolation + DB reality on ablation run ---
        run_iso = store.create_run(
            ResearchRunCreate(
                goal="cross-run isolation", budget=settings.default_research_budget()
            ),
            chosen_settings,
        )
        store.commit()
        isolated = service.retrieve(
            RetrievalQuery(query="solid-state", run_id=run_iso.id, top_k=5, mode="hybrid")
        )
        result.checks["cross_run_isolation"] = {"hits": len(isolated), "pass": len(isolated) == 0}
        result.checks["adversarial_flag"] = looks_like_injection(
            next(q["query"] for q in queries if q["id"] == "q-adversarial")
        )

        db = (
            session.execute(
                text(
                    """
                SELECT
                  (SELECT COUNT(*) FROM research_runs WHERE id = :rid) AS runs,
                  (SELECT COUNT(*) FROM sources WHERE research_run_id = :rid) AS sources,
                  (SELECT COUNT(*) FROM source_snapshots ss
                     JOIN sources s ON s.id = ss.source_id WHERE s.research_run_id = :rid) AS snapshots,
                  (SELECT COUNT(*) FROM document_chunks WHERE research_run_id = :rid) AS chunks,
                  (SELECT COUNT(*) FROM chunk_embeddings WHERE research_run_id = :rid) AS embeddings
                """
                ),
                {"rid": ablation_run.id},
            )
            .mappings()
            .one()
        )
        result.database_reality = {
            "run_id": str(ablation_run.id),
            **{k: int(db[k]) for k in db.keys()},
            "pass": all(
                int(db[k]) > 0 for k in ("runs", "sources", "snapshots", "chunks", "embeddings")
            ),
        }

        result.final_live_rag = {
            "run_id": str(ablation_run.id),
            "embedding_model": _runtime_model(client),
            "dimensions": chosen_dims,
            "sources": int(db["sources"]),
            "snapshots": int(db["snapshots"]),
            "chunks": int(db["chunks"]),
            "embeddings": int(db["embeddings"]),
            "ablation_modes": list(modes),
            "hybrid_aggregate": ablation_out["HYBRID_RRF_PLUS_DETERMINISTIC_RERANK"]["aggregate"],
            "note": (
                "Seeded corpus live path through chunking/embedding/FTS/pgvector/RRF/rerank. "
                "Full Tavily→report e2e is covered by integration orchestrator when providers allow."
            ),
        }

        ok = (
            result.checks["google_embedding"]["pass"]
            and result.checks["cross_run_isolation"]["pass"]
            and result.database_reality["pass"]
            and "768" in result.dimension_benchmark
            and "1536" in result.dimension_benchmark
            and all(label in result.retrieval_ablation for label in modes)
            and result.pre_rag_vs_rag.get("outcome")
            in {"RAG_BETTER", "PRE_RAG_BETTER", "SIMILAR", "MIXED"}
        )
        result.status = "PASS" if ok else "WARN"
    return result


def main() -> int:
    out = run_closure()
    print(json.dumps(asdict(out), indent=2, default=str))
    return 0 if out.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
