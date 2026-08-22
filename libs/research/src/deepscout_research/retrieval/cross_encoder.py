"""Optional cross-encoder reranking — requires sentence-transformers."""

from __future__ import annotations

import logging

from deepscout_research.retrieval.models import RetrievedChunk
from deepscout_research.retrieval.rerank import rerank_candidates
from deepscout_research.retrieval.spec import MAX_CHUNKS_PER_SOURCE

logger = logging.getLogger(__name__)

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        _model = CrossEncoder(_MODEL_NAME)
    return _model


def cross_encoder_rerank(
    candidates: list[RetrievedChunk],
    *,
    query: str,
    limit: int,
    max_per_source: int = MAX_CHUNKS_PER_SOURCE,
) -> list[RetrievedChunk]:
    if not candidates:
        return []
    try:
        model = _get_model()
    except ImportError:
        logger.warning("sentence-transformers not installed; falling back to deterministic rerank")
        return rerank_candidates(candidates, query=query, limit=limit, max_per_source=max_per_source)

    pairs = [(query, item.text) for item in candidates]
    scores = model.predict(pairs)
    scored = sorted(zip(scores, candidates, strict=True), key=lambda row: float(row[0]), reverse=True)
    per_source: dict[str, int] = {}
    selected: list[RetrievedChunk] = []
    for score, item in scored:
        count = per_source.get(str(item.source_id), 0)
        reason = f"cross_encoder:{score:.4f}"
        updated = item.model_copy(update={"rerank_score": float(score), "retrieval_reason": reason})
        if count >= max_per_source:
            continue
        per_source[str(item.source_id)] = count + 1
        selected.append(updated)
        if len(selected) >= limit:
            break
    return selected[:limit]
