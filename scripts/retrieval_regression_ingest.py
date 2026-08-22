#!/usr/bin/env python3
"""Ingest a production failure into a sanitized regression candidate (preview + explicit write)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from deepscout_core.settings import get_settings
from deepscout_evaluation.retrieval_diagnostics import (
    RetrievalDiagnosticTrace,
    infer_retrieval_failure_class,
)
from deepscout_evaluation.retrieval_quality import score_retrieved_chunks
from deepscout_evaluation.retrieval_sanitizer import sanitize_regression_candidate
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.retrieval.models import RetrievalQuery
from deepscout_research.retrieval.planner import plan_retrieval_query
from deepscout_research.retrieval.router import route_retrieval
from deepscout_research.retrieval.service import RetrievalService


def _build_candidate_from_run(
    *,
    store: ResearchStore,
    service: RetrievalService,
    run_id: UUID,
    query: str,
    failure_class: str | None,
    domain: str,
    language: str,
    notes: str,
) -> dict:
    run = store.get_run(run_id)
    if run is None:
        raise ValueError(f"run not found: {run_id}")

    plan = plan_retrieval_query(
        query=query,
        run_id=run_id,
        settings=service._settings,
        document_token_estimate=5000,
    )
    route = route_retrieval(plan)
    hits = service.retrieve(
        RetrievalQuery(query=query, run_id=run_id, top_k=5, candidate_k=20)
    )
    snapshots = store.list_snapshots_for_run(run_id)
    source_to_doc = {
        snap.source_id: f"snapshot-{snap.id}" for snap in snapshots
    }
    metrics = score_retrieved_chunks(
        hits,
        source_to_doc=source_to_doc,
        relevant_doc_ids=[],
        relevant_phrases=[],
        k=5,
    )
    trace = RetrievalDiagnosticTrace.from_plan_and_hits(
        query=query,
        plan=plan,
        route=route,
        hits=hits,
    )
    case_stub = {"should_answer": True, "failure_class": failure_class}
    inferred = infer_retrieval_failure_class(case=case_stub, trace=trace, metrics=metrics)

    candidate = {
        "case_id": f"reg-ingest-{run_id.hex[:8]}",
        "version": 1,
        "origin": "production_candidate",
        "created_at": datetime.now(UTC).date().isoformat(),
        "domain": domain,
        "language": language,
        "query": query,
        "query_type": "production_derived",
        "expected_intent": trace.detected_intent,
        "expected_corpus": trace.selected_corpus,
        "should_answer": True,
        "should_retrieve": True,
        "critical": False,
        "failure_class": failure_class or inferred,
        "original_failure_summary": notes,
        "sanitized_notes": (
            "REVIEW REQUIRED: operator must attach relevant_doc_ids/phrases manually"
        ),
        "diagnostic_preview": trace.model_dump(mode="json"),
        "metrics_preview": metrics,
    }
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview/write sanitized retrieval regression candidate from a run"
    )
    parser.add_argument("--run-id", required=True, help="Research run UUID")
    parser.add_argument("--query", required=True, help="Query that failed retrieval")
    parser.add_argument(
        "--failure-class", default=None, help="Optional RetrievalFailureClass value"
    )
    parser.add_argument("--domain", default="unknown")
    parser.add_argument("--language", default="en")
    parser.add_argument("--notes", default="", help="Sanitized failure summary for reviewers")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Append candidate to fixture (requires --confirm)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Explicit confirmation to write fixture",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Target fixture path (default: production regressions v1)",
    )
    args = parser.parse_args()

    settings = get_settings()
    session_factory = get_session_factory(settings.database_url)
    session = session_factory()
    store = ResearchStore(session)
    service = RetrievalService(store, settings)
    try:
        candidate = _build_candidate_from_run(
            store=store,
            service=service,
            run_id=UUID(args.run_id),
            query=args.query,
            failure_class=args.failure_class,
            domain=args.domain,
            language=args.language,
            notes=args.notes,
        )
        sanitized = sanitize_regression_candidate(candidate)
    except ValueError as exc:
        print(f"Refused to export: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()

    print("=== Sanitized candidate preview ===")
    print(json.dumps(sanitized, indent=2))

    if not args.write:
        print(
            "\nPreview only. Re-run with --write --confirm to append to fixture.",
            file=sys.stderr,
        )
        return 0

    if not args.confirm:
        print("Refused: --write requires --confirm", file=sys.stderr)
        return 1

    from deepscout_evaluation.retrieval_regression import PRODUCTION_REGRESSIONS_PATH

    target = args.fixture or PRODUCTION_REGRESSIONS_PATH
    fixture = json.loads(target.read_text())
    existing = {case["case_id"] for case in fixture.get("cases", [])}
    if sanitized["case_id"] in existing:
        print(f"Refused: case_id already exists: {sanitized['case_id']}", file=sys.stderr)
        return 1
    fixture["cases"].append(
        {k: v for k, v in sanitized.items() if k not in {"diagnostic_preview", "metrics_preview"}}
    )
    target.write_text(json.dumps(fixture, indent=2) + "\n")
    print(f"\nWrote candidate to {target}")
    print("Manual review required before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
