"""Versioned embedding/chunking configuration — vectors are not timeless."""

from __future__ import annotations

from dataclasses import dataclass

from deepscout_core.types import ProviderKind

CHUNKING_VERSION = "v1-recursive-1800-280"
EMBEDDING_CONFIG_VERSION = "v1-dim768-instruction-prefix"
DEFAULT_EMBEDDING_DIMENSIONS = 768
DEFAULT_RETRIEVAL_TOP_K = 8
DEFAULT_CANDIDATE_K = 20
MAX_CHUNKS_PER_SNAPSHOT = 80
EMBED_BATCH_SIZE = 32
RRF_K = 60
MAX_CHUNKS_PER_SOURCE = 3
CONTEXT_TOKEN_BUDGET = 3000
DOCUMENT_INSTRUCTION = "Task: index this passage for later retrieval of supporting evidence.\n"
QUERY_INSTRUCTION = (
    "Task: retrieve passages that can support or contradict this research question.\n"
)

SUPPORTED_EMBEDDING_PROVIDERS = frozenset({ProviderKind.GOOGLE, ProviderKind.OPENAI})


@dataclass(frozen=True, slots=True)
class EmbeddingSpec:
    provider: str
    model: str
    dimensions: int
    config_version: str = EMBEDDING_CONFIG_VERSION

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}:{self.dimensions}:{self.config_version}"
