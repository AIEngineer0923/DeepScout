#!/usr/bin/env python3
"""Benchmark RAW RAG vs COMPILED knowledge vs COMPILED+RAW — honest metrics only."""

from __future__ import annotations

import json
from pathlib import Path

from deepscout_core.domain.schemas import (
    ClaimWrite,
    EvidenceWrite,
    ResearchRunCreate,
    SourceSnapshotWrite,
    SourceWrite,
)
from deepscout_core.settings import get_settings
from deepscout_persistence import knowledge as knowledge_store
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.phases.compile_knowledge import compile_knowledge_for_run
from deepscout_research.retrieval.indexer import index_snapshots_for_run
from deepscout_research.retrieval.models import RetrievalQuery
from deepscout_research.retrieval.service import RetrievalService

BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1]
    / "libs/evaluation/data/compiled_knowledge_benchmark_v1.json"
)


def _phrase_recall(texts: list[str], phrases: list[str]) -> float:
    if not phrases:
        return 1.0 if not texts else 0.0
    blob = " ".join(texts).lower()
    return sum(1 for phrase in phrases if phrase.lower() in blob) / len(phrases)


def main() -> int:
    settings = get_settings()
    benchmark = json.loads(BENCHMARK_PATH.read_text())
    session_factory = get_session_factory(settings.database_url)
    with session_factory() as session:
        store = ResearchStore(session)
        run = store.create_run(
            ResearchRunCreate(
                goal="compiled knowledge benchmark", budget=settings.default_research_budget()
            ),
            settings,
        )
        for doc in benchmark["documents"]:
            source, _ = store.add_source(
                run.id,
                SourceWrite(canonical_url=f"https://ck.local/{doc['id']}", title=doc["title"]),
            )
            snapshot = store.add_snapshot(source.id, SourceSnapshotWrite(content=doc["text"]))
            claim = store.add_claim(
                run.id,
                ClaimWrite(statement=doc["text"][:240], source_id=source.id),
            )
            store.attach_evidence(
                claim.id,
                EvidenceWrite(
                    snapshot_id=snapshot.id,
                    quote=doc["text"][:240],
                    locator="offset:0-240",
                    support_strength=1.0,
                    confidence=1.0,
                ),
            )
        store.commit()
        index_snapshots_for_run(store, settings, run.id)
        compile_knowledge_for_run(store, run.id)
        store.commit()

        retriever = RetrievalService(store, settings)
        scores = {"RAW_RAG_ONLY": [], "COMPILED_ONLY": [], "COMPILED_PLUS_RAW": []}
        for case in benchmark["cases"]:
            phrases = case.get("relevant_phrases", [])
            raw_hits = retriever.retrieve(
                RetrievalQuery(query=case["query"], run_id=run.id, top_k=5, mode="hybrid")
            )
            raw_texts = [hit.text for hit in raw_hits]
            compiled_rows = knowledge_store.query_compiled_statements(
                session, run_id=run.id, query=case["query"], limit=5
            )
            compiled_texts = [row.statement_text for row in compiled_rows]
            scores["RAW_RAG_ONLY"].append(_phrase_recall(raw_texts, phrases))
            scores["COMPILED_ONLY"].append(_phrase_recall(compiled_texts, phrases))
            scores["COMPILED_PLUS_RAW"].append(_phrase_recall(raw_texts + compiled_texts, phrases))

        aggregate = {key: round(sum(vals) / len(vals), 4) for key, vals in scores.items()}
        decision = "IMPLEMENTED_OPTIONAL"
        if aggregate["COMPILED_ONLY"] + 0.05 < aggregate["RAW_RAG_ONLY"]:
            decision = "EVALUATED_AND_DEFERRED"
        if aggregate["COMPILED_PLUS_RAW"] <= aggregate["RAW_RAG_ONLY"] + 0.02:
            # Compiled adds little over raw on this corpus
            if decision != "EVALUATED_AND_DEFERRED":
                decision = "IMPLEMENTED_OPTIONAL"
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "run_id": str(run.id),
                    "aggregate_phrase_recall": aggregate,
                    "decision_hint": decision,
                    "interpretation": (
                        "Compiled knowledge is run-scoped and provenance-linked. "
                        "It does not replace hybrid RAG. Prefer OPTIONAL if it helps "
                        "repeated/synthesized questions without beating raw citation lookup."
                    ),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
