"""Provider-neutral embedding calls. Vendor SDKs stay in libs/providers."""

from __future__ import annotations

from collections.abc import Sequence

from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_providers.defaults import DEFAULT_EMBEDDING_MODELS
from deepscout_providers.factory import build_embeddings
from langchain_core.embeddings import Embeddings

from deepscout_research.retrieval.spec import (
    DOCUMENT_INSTRUCTION,
    QUERY_INSTRUCTION,
    SUPPORTED_EMBEDDING_PROVIDERS,
    EmbeddingSpec,
)


class IncompatibleEmbeddingSpaceError(ValueError):
    """Raised when two embedding specs cannot be compared."""


def embedding_spec_from_settings(settings: Settings) -> EmbeddingSpec:
    provider = settings.resolved_embedding_provider()
    if provider not in SUPPORTED_EMBEDDING_PROVIDERS:
        raise ValueError(
            f"{provider.value} has no embedding API; set EMBEDDING_PROVIDER to google or openai"
        )
    model = settings.embedding_model or DEFAULT_EMBEDDING_MODELS[provider]
    dimensions = settings.embedding_dimensions
    return EmbeddingSpec(provider=provider.value, model=model, dimensions=dimensions)


def assert_compatible(left: EmbeddingSpec, right: EmbeddingSpec) -> None:
    if left.key != right.key:
        raise IncompatibleEmbeddingSpaceError(
            f"incompatible embedding spaces: {left.key} vs {right.key}"
        )


def build_embedding_client(settings: Settings) -> tuple[Embeddings, EmbeddingSpec]:
    spec = embedding_spec_from_settings(settings)
    client = build_embeddings(settings)
    _apply_output_dimensionality(client, spec)
    return client, spec


def embed_documents(client: Embeddings, texts: Sequence[str]) -> list[list[float]]:
    prefixed = [DOCUMENT_INSTRUCTION + text for text in texts]
    return [list(map(float, vector)) for vector in client.embed_documents(list(prefixed))]


def embed_query(client: Embeddings, query: str) -> list[float]:
    return [float(value) for value in client.embed_query(QUERY_INSTRUCTION + query)]


def _apply_output_dimensionality(client: Embeddings, spec: EmbeddingSpec) -> None:
    if spec.provider == ProviderKind.GOOGLE.value and hasattr(client, "output_dimensionality"):
        client.output_dimensionality = spec.dimensions
    if spec.provider == ProviderKind.OPENAI.value and hasattr(client, "dimensions"):
        client.dimensions = spec.dimensions
