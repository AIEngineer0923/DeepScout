#!/usr/bin/env python3
"""Retrieval quality benchmark — router, ablation, contextual, compiled, graph."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from deepscout_core.settings import Settings, get_settings
from deepscout_evaluation.retrieval_quality import (
    RetrievalQualityReport,
    compare_contextual_embeddings,
    evaluate_ablation_suite,
    evaluate_compiled_retrieval,
    evaluate_failure_cases,
    evaluate_graph_retrieval,
    evaluate_router_cases,
    load_benchmark_v2,
    seed_benchmark_corpus,
    seed_compiled_fixture,
    seed_graph_fixture,
)
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.retrieval.embeddings import build_embedding_client
from deepscout_research.retrieval.indexer import index_snapshots_for_run
from deepscout_research.retrieval.service import RetrievalService

TOP_K = 5
CANDIDATE_K = 20


def _git_head() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return None


def run_router_only(settings: Settings, benchmark: dict) -> dict:
    return evaluate_router_cases(benchmark["router_cases"], settings=settings)


def run_live(
    settings: Settings,
    benchmark: dict,
    *,
    cross_encoder: bool = False,
) -> RetrievalQualityReport:
    report = RetrievalQualityReport(version=benchmark["version"], branch_head=_git_head())
    if settings.google_api_key is None and settings.openai_api_key is None:
        report.errors.append("No embedding provider API key configured for live benchmark")
        return report

    report.router = run_router_only(settings, benchmark)
    session_factory = get_session_factory(settings.database_url)
    session = session_factory()
    store = ResearchStore(session)
    client, spec = build_embedding_client(settings)
    service = RetrievalService(store, settings, client=client, spec=spec)

    run, _, source_to_doc = seed_benchmark_corpus(store, settings, benchmark["documents"])
    index_snapshots_for_run(store, settings, run.id, client=client, spec=spec)
    store.commit()

    report.ablation = evaluate_ablation_suite(
        service,
        session=session,
        run_id=run.id,
        cases=benchmark["retrieval_cases"],
        source_to_doc=source_to_doc,
        spec=spec,
        client=client,
        top_k=TOP_K,
        candidate_k=CANDIDATE_K,
    )
    report.contextual = compare_contextual_embeddings(
        service,
        session=session,
        run_id=run.id,
        cases=benchmark["contextual_cases"],
        source_to_doc=source_to_doc,
        client=client,
        spec=spec,
        top_k=TOP_K,
        candidate_k=CANDIDATE_K,
    )
    report.failure_cases = evaluate_failure_cases(
        service, run_id=run.id, cases=benchmark["failure_cases"], source_to_doc=source_to_doc
    )

    compiled_run, _ = seed_compiled_fixture(
        store, settings, benchmark["documents"], benchmark["compiled_fixture"]
    )
    index_snapshots_for_run(store, settings, compiled_run.id, client=client, spec=spec)
    store.commit()
    report.compiled = evaluate_compiled_retrieval(
        service, run_id=compiled_run.id, fixture=benchmark["compiled_fixture"]
    )

    graph_run_id = seed_graph_fixture(store, session, settings, benchmark["graph_fixture"])
    report.graph = evaluate_graph_retrieval(
        session, run_id=graph_run_id, fixture=benchmark["graph_fixture"]
    )

    report.latency = {
        mode: report.ablation[mode]["mean_latency_s"]
        for mode in report.ablation
        if isinstance(report.ablation.get(mode), dict)
    }

    if cross_encoder:
        try:
            from deepscout_research.retrieval.cross_encoder import cross_encoder_rerank

            report.cross_encoder = {
                "status": "available",
                "note": "Use RERANKER_MODE=cross_encoder for production comparison",
            }
            del cross_encoder_rerank  # import check only unless extended
        except ImportError:
            report.cross_encoder = {
                "status": "not_installed",
                "note": "Install deepscout-research[rerank] to compare cross-encoder rerank",
            }
    else:
        report.cross_encoder = {
            "status": "not_run",
            "note": "Pass --cross-encoder to probe optional reranker",
        }

    session.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepScout retrieval quality benchmark")
    parser.add_argument(
        "--router-only",
        action="store_true",
        help="Evaluate router without DB/embeddings",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run full live benchmark (DB + embeddings)",
    )
    parser.add_argument(
        "--cross-encoder",
        action="store_true",
        help="Probe cross-encoder availability",
    )
    parser.add_argument("--benchmark", type=Path, default=None, help="Path to benchmark JSON")
    args = parser.parse_args()

    settings = get_settings()
    benchmark = load_benchmark_v2(args.benchmark)

    if args.live:
        report = run_live(settings, benchmark, cross_encoder=args.cross_encoder)
        payload = {
            "version": report.version,
            "branch_head": report.branch_head,
            "router": report.router,
            "ablation": report.ablation,
            "contextual": report.contextual,
            "compiled": report.compiled,
            "graph": report.graph,
            "failure_cases": report.failure_cases,
            "cross_encoder": report.cross_encoder,
            "latency": report.latency,
            "errors": report.errors,
        }
    else:
        payload = {
            "version": benchmark["version"],
            "branch_head": _git_head(),
            "router": run_router_only(settings, benchmark),
            "note": "Router-only mode. Pass --live for ablation/contextual/compiled/graph.",
        }

    print(json.dumps(payload, indent=2))
    if payload.get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
