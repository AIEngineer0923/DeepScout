#!/usr/bin/env python3
"""Cross-language BM25/FTS/dense/RRF/rerank benchmark.

Router-only mode is provider-free. ``--live`` uses the configured PostgreSQL
database and embedding provider and reports every retrieval ablation honestly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from deepscout_core.settings import get_settings
from deepscout_evaluation.retrieval_quality import (
    evaluate_ablation_suite,
    evaluate_router_cases,
    seed_benchmark_corpus,
)
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.retrieval.embeddings import build_embedding_client
from deepscout_research.retrieval.indexer import index_snapshots_for_run
from deepscout_research.retrieval.service import RetrievalService

DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "libs/evaluation/data/multilingual_retrieval_benchmark_v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    settings = get_settings()
    payload: dict = {
        "version": fixture["version"],
        "router": evaluate_router_cases(fixture["router_cases"], settings=settings),
    }
    if not args.live:
        payload["ablation"] = {
            "status": "not_run",
            "reason": "Pass --live for PostgreSQL FTS and provider embedding ablations.",
            "modes": [
                "bm25_only",
                "fts_only",
                "dense_only",
                "bm25_dense",
                "fts_dense",
                "bm25_fts_dense",
                "full_rrf_rerank",
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0

    session = get_session_factory(settings.database_url)()
    try:
        store = ResearchStore(session)
        client, spec = build_embedding_client(settings)
        service = RetrievalService(store, settings, client=client, spec=spec)
        run, _, source_to_doc = seed_benchmark_corpus(
            store,
            settings,
            fixture["documents"],
            goal="multilingual-cross-language-retrieval-benchmark",
        )
        index_stats = index_snapshots_for_run(store, settings, run.id, client=client, spec=spec)
        store.commit()
        payload["embedding"] = {
            "provider": spec.provider,
            "model": spec.model,
            "dimensions": spec.dimensions,
            "config_version": spec.config_version,
            "reindex_required": False,
        }
        payload["index"] = index_stats
        payload["ablation"] = evaluate_ablation_suite(
            service,
            session=session,
            run_id=run.id,
            cases=fixture["retrieval_cases"],
            source_to_doc=source_to_doc,
            spec=spec,
            client=client,
            top_k=5,
            candidate_k=20,
        )
    finally:
        session.close()
    if args.summary and isinstance(payload.get("ablation"), dict):
        cases_by_id = {case["id"]: case for case in fixture["retrieval_cases"]}
        payload["ablation"] = {
            mode: {
                "aggregate": value.get("aggregate", {}),
                "mean_latency_s": value.get("mean_latency_s"),
                "answerable": _answerable_summary(value.get("per_query", []), cases_by_id),
            }
            for mode, value in payload["ablation"].items()
            if isinstance(value, dict) and "aggregate" in value
        }
    print(json.dumps(payload, indent=2))
    return 0


def _answerable_summary(rows: list[dict], cases_by_id: dict[str, dict]) -> dict:
    answerable = [
        row for row in rows if cases_by_id.get(row["id"], {}).get("relevant_doc_ids")
    ]
    negatives = [
        row for row in rows if not cases_by_id.get(row["id"], {}).get("relevant_doc_ids")
    ]
    return {
        "cases": len(answerable),
        "top_1": sum(int(row.get("hit_at_1", 0)) for row in answerable),
        "top_3": sum(int(row.get("hit_at_3", 0)) for row in answerable),
        "negative_cases": len(negatives),
        "negative_passed": sum(int(row.get("hit_at_1", 0)) for row in negatives),
    }


if __name__ == "__main__":
    sys.exit(main())
