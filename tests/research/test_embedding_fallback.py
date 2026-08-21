"""Embedding space fallback must fail closed."""

from deepscout_research.retrieval.embeddings import (
    EmbeddingSpec,
    IncompatibleEmbeddingSpaceError,
)
from deepscout_research.routing.embedding_fallback import reject_incompatible_embedding_fallback


def test_cross_provider_embedding_fallback_rejected() -> None:
    google = EmbeddingSpec(provider="google", model="gemini-embedding-2", dimensions=768)
    openai = EmbeddingSpec(provider="openai", model="text-embedding-3-small", dimensions=1536)
    try:
        reject_incompatible_embedding_fallback(google, openai)
        raise AssertionError("expected incompatible space rejection")
    except IncompatibleEmbeddingSpaceError:
        pass


def test_same_space_allowed() -> None:
    left = EmbeddingSpec(provider="google", model="gemini-embedding-2", dimensions=768)
    right = EmbeddingSpec(provider="google", model="gemini-embedding-2", dimensions=768)
    reject_incompatible_embedding_fallback(left, right)


def test_dimension_mismatch_rejected() -> None:
    a = EmbeddingSpec(provider="google", model="gemini-embedding-2", dimensions=768)
    b = EmbeddingSpec(provider="google", model="gemini-embedding-2", dimensions=1536)
    try:
        reject_incompatible_embedding_fallback(a, b)
        raise AssertionError("expected dimension rejection")
    except IncompatibleEmbeddingSpaceError:
        pass
