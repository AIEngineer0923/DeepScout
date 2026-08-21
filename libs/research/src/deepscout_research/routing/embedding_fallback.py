"""Reject incompatible embedding-space fallback — never silent mix."""

from __future__ import annotations

from deepscout_research.retrieval.embeddings import (
    EmbeddingSpec,
    assert_compatible,
)


def reject_incompatible_embedding_fallback(
    current: EmbeddingSpec,
    candidate: EmbeddingSpec,
) -> None:
    """Fail closed when a fallback would query/write a different embedding space."""
    assert_compatible(current, candidate)
