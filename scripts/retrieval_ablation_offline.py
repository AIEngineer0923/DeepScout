#!/usr/bin/env python3
"""Offline BM25 vs FTS ablation on retrieval-benchmark-v1.1 (no provider calls)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from deepscout_research.retrieval.bm25 import BM25Index

BENCHMARK = Path(__file__).resolve().parents[1] / "libs/evaluation/data/retrieval_benchmark_v1.json"


def _hit_rate(hits: list[str], phrases: list[str]) -> float:
    if not phrases:
        return 0.0
    blob = " ".join(hits).lower()
    return sum(1 for phrase in phrases if phrase.lower() in blob) / len(phrases)


def main() -> None:
    data = json.loads(BENCHMARK.read_text())
    docs = {item["id"]: item["text"] for item in data["documents"]}
    doc_ids = {item["id"]: uuid.uuid4() for item in data["documents"]}
    reverse = {v: k for k, v in doc_ids.items()}

    bm25 = BM25Index()
    for doc_key, text in docs.items():
        bm25.add(doc_ids[doc_key], text)

    bm25_scores: list[float] = []
    for query in data["queries"]:
        hits = bm25.search(query["query"], limit=3)
        texts = [docs[reverse[h[0]]] for h in hits if h[0] in reverse]
        bm25_scores.append(_hit_rate(texts, query.get("relevant_phrases", [])))

    mean = sum(bm25_scores) / max(len(bm25_scores), 1)
    print(
        json.dumps(
            {
                "benchmark": data["version"],
                "bm25_mean_phrase_recall_at_3": round(mean, 4),
                "per_query": bm25_scores,
                "note": "Compare with phase5_closure_gate FTS/dense/hybrid live ablation.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
