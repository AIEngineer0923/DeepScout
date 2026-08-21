"""Whether runtime retrieval/indexing can execute with current settings."""

from __future__ import annotations

from deepscout_core.settings import Settings

from deepscout_research.retrieval.spec import SUPPORTED_EMBEDDING_PROVIDERS


def retrieval_enabled(settings: Settings) -> bool:
    provider = settings.resolved_embedding_provider()
    if provider not in SUPPORTED_EMBEDDING_PROVIDERS:
        return False
    try:
        settings.require_api_key(provider)
    except ValueError:
        return False
    return True
