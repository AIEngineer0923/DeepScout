"""Multi-provider LLM and embedding factory for DeepScout."""

from deepscout_providers.config import DEFAULT_MODEL_BUILD_OPTIONS, ModelBuildOptions
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS, DEFAULT_EMBEDDING_MODELS
from deepscout_providers.factory import build_chat_model, build_embeddings

__all__ = [
    "DEFAULT_MODEL_BUILD_OPTIONS",
    "ModelBuildOptions",
    "build_chat_model",
    "build_embeddings",
    "DEFAULT_CHAT_MODELS",
    "DEFAULT_EMBEDDING_MODELS",
]
