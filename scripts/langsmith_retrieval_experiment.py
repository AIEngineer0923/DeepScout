#!/usr/bin/env python3
"""Real LangSmith Phase 5 experiments — dimension + ablation against live retrieval."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from deepscout_core.domain.schemas import ResearchRunCreate, SourceSnapshotWrite, SourceWrite
from deepscout_core.settings import get_settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_providers.defaults import DEFAULT_EMBEDDING_MODELS
from deepscout_providers.factory import build_embeddings
from deepscout_research.langsmith_env import configure_langsmith_env
from deepscout_research.retrieval.indexer import index_snapshots_for_run
from deepscout_research.retrieval.models import RetrievalQuery
from deepscout_research.retrieval.service import RetrievalService
from deepscout_research.retrieval.spec import EmbeddingSpec

BENCHMARK_PATH = Path(__file__).resolve().parents[1] / "libs/evaluation/data/retrieval_benchmark_v1.json"


def _runtime_model(client) -> str:
    for attr in ("model", "model_name"):
        value = getattr(client, attr, None)
        if value:
            return str(value)
    return DEFAULT_EMBEDDING_MODELS[get_settings().resolved_embedding_provider()]


def _client_spec(settings, dims: int):
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


def _phrase_score(texts: list[str], phrases: list[str]) -> float:
    if not phrases:
        return 1.0 if not texts else 0.0
    blob = " ".join(texts).lower()
    return sum(1 for phrase in phrases if phrase.lower() in blob) / len(phrases)


def _seed(store, settings, documents):
    run = store.create_run(
        ResearchRunCreate(goal="langsmith retrieval experiment", budget=settings.default_research_budget()),
        settings,
    )
    for doc in documents:
        source, _ = store.add_source(
            run.id,
            SourceWrite(canonical_url=f"https://ls.local/{doc['id']}", title=doc["title"]),
        )
        store.add_snapshot(source.id, SourceSnapshotWrite(content=doc["text"]))
    store.commit()
    return run


def main() -> int:
    settings = configure_langsmith_env()
    if settings.langsmith_api_key is None:
        print(json.dumps({"status": "BLOCKED", "reason": "langsmith_not_configured"}))
        return 1
    if settings.google_api_key is None:
        print(json.dumps({"status": "BLOCKED", "reason": "google_not_configured"}))
        return 1

    from langsmith import Client
    from langsmith.evaluation import evaluate

    benchmark = json.loads(BENCHMARK_PATH.read_text())
    client_ls = Client()
    dataset_name = "deepscout-retrieval-v1"
    existing = list(client_ls.list_datasets(dataset_name=dataset_name))
    if existing:
        dataset = existing[0]
    else:
        examples = [
            {
                "inputs": {
                    "query": item["query"],
                    "type": item.get("type"),
                    "category": item.get("category"),
                },
                "outputs": {
                    "relevant_phrases": item.get("relevant_phrases", []),
                    "relevant_doc_ids": item.get("relevant_doc_ids", []),
                },
            }
            for item in benchmark["queries"]
        ]
        dataset = client_ls.create_dataset(dataset_name, description="Phase 5 retrieval benchmark v1.1")
        client_ls.create_examples(dataset_id=dataset.id, examples=examples)

    session_factory = get_session_factory(settings.database_url)
    experiments: dict[str, str] = {}

    with session_factory() as session:
        store = ResearchStore(session)
        for dims in (768, 1536):
            emb_client, spec, dim_settings = _client_spec(settings, dims)
            run = _seed(store, dim_settings, benchmark["documents"])
            index_snapshots_for_run(store, dim_settings, run.id, client=emb_client, spec=spec)
            store.commit()
            service = RetrievalService(store, dim_settings, client=emb_client, spec=spec)

            def _make_target(
                svc: RetrievalService,
                rid,
                mode: str,
                apply_rerank: bool,
                dimensions: int,
                emb_spec: EmbeddingSpec,
            ):
                def _target(inputs: dict) -> dict:
                    hits = svc.retrieve(
                        RetrievalQuery(
                            query=inputs["query"],
                            run_id=rid,
                            top_k=5,
                            candidate_k=20,
                            mode=mode,  # type: ignore[arg-type]
                            apply_rerank=apply_rerank,
                        )
                    )
                    return {
                        "retrieved_texts": [h.text for h in hits],
                        "retrieval_mode": mode,
                        "apply_rerank": apply_rerank,
                        "embedding_provider": emb_spec.provider,
                        "embedding_model": emb_spec.model,
                        "embedding_dimensions": dimensions,
                        "embedding_config_version": emb_spec.config_version,
                        "chunking_version": "v1-recursive-1800-280",
                        "candidate_k": 20,
                        "top_k": 5,
                        "rrf_k": 60,
                        "reranker_version": "deterministic-v1",
                        "dataset_version": benchmark["version"],
                    }

                return _target

            def _evaluator(run_obj, example) -> dict:
                outputs = run_obj.outputs or {}
                expected = example.outputs or {}
                score = _phrase_score(
                    outputs.get("retrieved_texts", []),
                    expected.get("relevant_phrases", []),
                )
                return {"key": "phrase_recall", "score": score}

            configs = [
                (f"dim{dims}-hybrid-rerank", "hybrid", True),
            ]
            if dims == 1536:
                configs.extend(
                    [
                        ("ablation-lexical", "lexical", False),
                        ("ablation-dense", "dense", False),
                        ("ablation-hybrid-rrf", "hybrid", False),
                        ("ablation-hybrid-rerank", "hybrid", True),
                    ]
                )

            for label, mode, apply_rerank in configs:
                prefix = f"deepscout-retrieval-{datetime.now(UTC).strftime('%Y%m%d')}-{label}"
                results = evaluate(
                    _make_target(service, run.id, mode, apply_rerank, dims, spec),
                    data=dataset.name,
                    evaluators=[_evaluator],
                    experiment_prefix=prefix,
                    metadata={
                        "phase": "5",
                        "embedding_provider": spec.provider,
                        "embedding_model": spec.model,
                        "embedding_dimensions": dims,
                        "embedding_config_version": spec.config_version,
                        "chunking_version": "v1-recursive-1800-280",
                        "retrieval_mode": mode,
                        "candidate_k": 20,
                        "top_k": 5,
                        "rrf_k": 60,
                        "reranker_version": "deterministic-v1" if apply_rerank else "none",
                        "dataset_version": benchmark["version"],
                    },
                    client=client_ls,
                )
                experiments[label] = str(results)

    print(
        json.dumps(
            {
                "status": "PASS",
                "dataset": dataset_name,
                "experiments": experiments,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
