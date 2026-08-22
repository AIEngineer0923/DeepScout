"""Retrieval metrics scoring — deterministic ground truth helpers."""

from __future__ import annotations

import uuid

from deepscout_evaluation.retrieval_quality import score_retrieved_chunks
from deepscout_research.retrieval.models import RetrievedChunk


def _chunk(source_id: uuid.UUID, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        snapshot_id=uuid.uuid4(),
        source_id=source_id,
        run_id=uuid.uuid4(),
        text=text,
        locator="test",
        ordinal=0,
        start_offset=0,
        end_offset=len(text),
    )


def test_score_empty_relevant_set_prefers_no_hits() -> None:
    sid = uuid.uuid4()
    hits = [_chunk(sid, "irrelevant quantum topic")]
    metrics = score_retrieved_chunks(
        hits,
        source_to_doc={sid: "doc-a"},
        relevant_doc_ids=[],
        relevant_phrases=[],
        k=3,
    )
    assert metrics["hit_at_3"] == 0.0


def test_score_finds_relevant_doc_at_rank_one() -> None:
    good = uuid.uuid4()
    bad = uuid.uuid4()
    hits = [_chunk(good, "CVE-2024-1234 in firmware"), _chunk(bad, "unrelated")]
    metrics = score_retrieved_chunks(
        hits,
        source_to_doc={good: "doc-security", bad: "doc-market"},
        relevant_doc_ids=["doc-security"],
        relevant_phrases=["CVE-2024-1234"],
        k=3,
    )
    assert metrics["hit_at_1"] == 1.0
    assert metrics["mrr"] == 1.0
