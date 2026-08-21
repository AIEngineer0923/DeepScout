#!/usr/bin/env python3
"""Phase 5 live verification gate — real embeddings, pgvector, ablation."""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from deepscout_core.domain.schemas import (
    ResearchRunCreate,
    SearchCandidateWrite,
    SearchResult,
    SourceSnapshotWrite,
    SourceWrite,
)
from deepscout_core.settings import get_settings
from deepscout_core.types import ProviderKind
from deepscout_persistence.retrieval import dense_search, lexical_search, load_chunks
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

BENCHMARK_PATH = Path(__file__).resolve().parents[1] / "libs/evaluation/data/retrieval_benchmark_v1.json"


@dataclass
class GateResult:
    status: str = "PENDING"
    checks: dict = field(default_factory=dict)
    ablation: dict = field(default_factory=dict)
    dimension_experiment: dict = field(default_factory=dict)
    pre_rag_vs_rag: dict = field(default_factory=dict)
    run_id: str | None = None
    errors: list[str] = field(default_factory=list)


def _runtime_model(client) -> str:
    for attr in ("model", "model_name"):
        value = getattr(client, attr, None)
        if value:
            return str(value)
    return DEFAULT_EMBEDDING_MODELS[ProviderKind.GOOGLE]


def _embed_docs(client, texts: list[str]) -> list[list[float]]:
    prefixed = [DOCUMENT_INSTRUCTION + t for t in texts]
    return [list(map(float, v)) for v in client.embed_documents(prefixed)]


def _embed_query(client, query: str) -> list[float]:
    return [float(v) for v in client.embed_query(QUERY_INSTRUCTION + query)]


def _hit_rate(texts: list[str], phrases: list[str]) -> float:
    if not phrases:
        return 1.0 if not texts else 0.0
    blob = " ".join(texts).lower()
    return sum(1 for p in phrases if p.lower() in blob) / len(phrases)


def _client_for_dims(settings, dims: int):
    s = settings.model_copy(update={"embedding_dimensions": dims})
    client = build_embeddings(s)
    if hasattr(client, "output_dimensionality"):
        client.output_dimensionality = dims
    return client


def run_gate() -> GateResult:
    result = GateResult()
    settings = get_settings()
    if settings.google_api_key is None:
        result.status = "BLOCKED"
        result.errors.append("GOOGLE_API_KEY not configured")
        return result

    benchmark = json.loads(BENCHMARK_PATH.read_text())
    session_factory = get_session_factory(settings.database_url)

    with session_factory() as session:
        store = ResearchStore(session)
        run = store.create_run(
            ResearchRunCreate(goal="Phase 5 live gate", budget=settings.default_research_budget()),
            settings,
        )
        result.run_id = str(run.id)

        for doc in benchmark["documents"]:
            source, _ = store.add_source(
                run.id,
                SourceWrite(canonical_url=f"https://gate.local/{doc['id']}", title=doc["title"]),
            )
            store.add_snapshot(source.id, SourceSnapshotWrite(content=doc["text"]))
        store.commit()

        client = _client_for_dims(settings, settings.embedding_dimensions)
        runtime_model = _runtime_model(client)
        t0 = time.perf_counter()
        vec = _embed_docs(client, ["Solid-state battery gate smoke text."])[0]
        embed_latency = time.perf_counter() - t0
        result.checks["google_embedding"] = {
            "provider": "google",
            "runtime_model": runtime_model,
            "requested_dimensions": settings.embedding_dimensions,
            "returned_dimensions": len(vec),
            "finite": all(math.isfinite(v) for v in vec),
            "non_zero": any(abs(v) > 1e-9 for v in vec),
            "latency_s": round(embed_latency, 3),
            "pass": len(vec) == settings.embedding_dimensions and runtime_model.startswith("gemini-embedding"),
        }

        t0 = time.perf_counter()
        first_index = index_snapshots_for_run(store, settings, run.id)
        store.commit()
        second_index = index_snapshots_for_run(store, settings, run.id)
        store.commit()
        result.checks["indexing"] = {
            "first_pass": first_index,
            "second_pass": second_index,
            "latency_s": round(time.perf_counter() - t0, 3),
            "pass": first_index.get("indexed", 0) >= 1,
        }

        service = RetrievalService(store, settings, client=client)
        spec = service._spec
        ablation: dict[str, list[float]] = {"lexical": [], "dense": [], "hybrid_rerank": []}

        for item in benchmark["queries"]:
            query = item["query"]
            phrases = item.get("relevant_phrases", [])
            qvec = _embed_query(client, query)
            lex_ids = [cid for cid, _ in lexical_search(session, run_id=run.id, query=query, limit=5)]
            den_ids = [
                cid
                for cid, _ in dense_search(
                    session,
                    run_id=run.id,
                    query_vector=qvec,
                    provider=spec.provider,
                    model=spec.model,
                    dimensions=spec.dimensions,
                    config_version=spec.config_version,
                    limit=5,
                )
            ]
            rows = load_chunks(session, lex_ids + den_ids)
            ablation["lexical"].append(_hit_rate([rows[i].text for i in lex_ids if i in rows], phrases))
            ablation["dense"].append(_hit_rate([rows[i].text for i in den_ids if i in rows], phrases))
            hits = service.retrieve(RetrievalQuery(query=query, run_id=run.id, top_k=5, mode="hybrid"))
            ablation["hybrid_rerank"].append(_hit_rate([h.text for h in hits], phrases))

        result.ablation = {k: round(sum(v) / len(v), 3) for k, v in ablation.items()}

        dim_latency: dict[str, float] = {}
        dim_dims: dict[str, int] = {}
        probe = benchmark["documents"][0]["text"]
        for dims in (768, 1536):
            c = _client_for_dims(settings, dims)
            t0 = time.perf_counter()
            out = _embed_docs(c, [probe])[0]
            dim_latency[str(dims)] = round(time.perf_counter() - t0, 3)
            dim_dims[str(dims)] = len(out)
        result.dimension_experiment = {
            "returned_dimensions": dim_dims,
            "embed_latency_s": dim_latency,
            "decision": "1536 default retained for provider parity with OpenAI text-embedding-3-small",
        }

        store.add_search_candidates(
            run.id,
            SearchCandidateWrite(
                query="CVE-2024-1234 battery firmware",
                provider="gate",
                results=[
                    SearchResult(
                        url="https://gate.local/doc-battery",
                        title="Solid-State Battery Overview",
                        snippet="CVE in BMS firmware",
                    )
                ],
            ),
        )
        store.commit()
        result.pre_rag_vs_rag = {
            "pre_rag": extract_claims_for_run(store, run.id, retriever=None),
            "post_rag": extract_claims_for_run(store, run.id, retriever=service),
        }

        result.checks["adversarial_flag"] = looks_like_injection(benchmark["queries"][-1]["query"])
        run_b = store.create_run(
            ResearchRunCreate(goal="cross-run gate", budget=settings.default_research_budget()),
            settings,
        )
        store.commit()
        isolated = service.retrieve(RetrievalQuery(query="solid-state", run_id=run_b.id, top_k=5))
        result.checks["cross_run_isolation"] = {"hits": len(isolated), "pass": len(isolated) == 0}

        ok = (
            result.checks["google_embedding"]["pass"]
            and result.checks["indexing"]["pass"]
            and result.checks["cross_run_isolation"]["pass"]
        )
        result.status = "PASS" if ok else "WARN"
    return result


def main() -> int:
    out = run_gate()
    print(json.dumps(asdict(out), indent=2, default=str))
    return 0 if out.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
