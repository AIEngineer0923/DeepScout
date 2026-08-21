"""Live Phase 5 embedding integration — requires GOOGLE_API_KEY in .env."""

from __future__ import annotations

import math

import pytest
from deepscout_core.settings import get_settings
from deepscout_providers.defaults import DEFAULT_EMBEDDING_MODELS
from deepscout_providers.factory import build_embeddings
from deepscout_research.retrieval.embeddings import DOCUMENT_INSTRUCTION


@pytest.mark.integration
def test_live_google_embedding_gemini_embedding_2() -> None:
    settings = get_settings()
    if settings.google_api_key is None:
        pytest.skip("GOOGLE_API_KEY required")
    client = build_embeddings(settings)
    if hasattr(client, "output_dimensionality"):
        client.output_dimensionality = settings.embedding_dimensions
    vectors = client.embed_documents([DOCUMENT_INSTRUCTION + "Live integration smoke text."])
    assert vectors
    vec = [float(v) for v in vectors[0]]
    provider = settings.resolved_embedding_provider()
    model = getattr(client, "model", None) or DEFAULT_EMBEDDING_MODELS[provider]
    assert str(model).startswith("gemini-embedding")
    assert len(vec) == settings.embedding_dimensions
    assert all(math.isfinite(v) for v in vec)
    assert any(abs(v) > 1e-9 for v in vec)
