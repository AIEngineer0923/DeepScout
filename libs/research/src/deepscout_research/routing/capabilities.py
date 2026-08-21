"""Typed model capability registry — no false provider equivalence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from deepscout_core.types import ProviderKind
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS, DEFAULT_EMBEDDING_MODELS


class ModelCapability(StrEnum):
    CHAT = "chat"
    STRUCTURED_OUTPUT = "structured_output"
    TOOL_CALLING = "tool_calling"
    STREAMING = "streaming"
    EMBEDDING = "embedding"
    LONG_CONTEXT = "long_context"
    VISION = "vision"


@dataclass(frozen=True, slots=True)
class ModelRequirements:
    """Declared requirements for a model call — router filters against the registry."""

    task_type: str = "chat"
    capabilities: frozenset[ModelCapability] = frozenset(
        {ModelCapability.CHAT, ModelCapability.STRUCTURED_OUTPUT}
    )
    allowed_providers: frozenset[ProviderKind] | None = None
    fallback_allowed: bool = False
    privacy_class: str = "standard"


@dataclass(frozen=True, slots=True)
class ModelCapabilityRecord:
    provider: ProviderKind
    model: str
    capabilities: frozenset[ModelCapability]
    embedding_dimensions: int | None = None


def _chat_caps(*extra: ModelCapability) -> frozenset[ModelCapability]:
    base = {
        ModelCapability.CHAT,
        ModelCapability.STRUCTURED_OUTPUT,
        ModelCapability.TOOL_CALLING,
        ModelCapability.STREAMING,
    }
    base.update(extra)
    return frozenset(base)


# Conservative known defaults for DeepScout MODE A defaults — not exhaustive catalogs.
DEFAULT_CAPABILITY_REGISTRY: tuple[ModelCapabilityRecord, ...] = (
    ModelCapabilityRecord(
        provider=ProviderKind.GOOGLE,
        model=DEFAULT_CHAT_MODELS[ProviderKind.GOOGLE],
        capabilities=_chat_caps(ModelCapability.LONG_CONTEXT, ModelCapability.VISION),
    ),
    ModelCapabilityRecord(
        provider=ProviderKind.OPENAI,
        model=DEFAULT_CHAT_MODELS[ProviderKind.OPENAI],
        capabilities=_chat_caps(ModelCapability.LONG_CONTEXT),
    ),
    ModelCapabilityRecord(
        provider=ProviderKind.ANTHROPIC,
        model=DEFAULT_CHAT_MODELS[ProviderKind.ANTHROPIC],
        capabilities=_chat_caps(ModelCapability.LONG_CONTEXT),
    ),
    ModelCapabilityRecord(
        provider=ProviderKind.GOOGLE,
        model=DEFAULT_EMBEDDING_MODELS[ProviderKind.GOOGLE],
        capabilities=frozenset({ModelCapability.EMBEDDING}),
        embedding_dimensions=768,
    ),
    ModelCapabilityRecord(
        provider=ProviderKind.OPENAI,
        model=DEFAULT_EMBEDDING_MODELS[ProviderKind.OPENAI],
        capabilities=frozenset({ModelCapability.EMBEDDING}),
        embedding_dimensions=1536,
    ),
)


def lookup_capabilities(
    provider: ProviderKind,
    model: str,
    *,
    registry: tuple[ModelCapabilityRecord, ...] = DEFAULT_CAPABILITY_REGISTRY,
) -> frozenset[ModelCapability]:
    for record in registry:
        if record.provider == provider and record.model == model:
            return record.capabilities
    # Unknown model: assume chat-only until explicitly registered — fail closed for extras.
    return frozenset({ModelCapability.CHAT})


def satisfies_requirements(
    provider: ProviderKind,
    model: str,
    requirements: ModelRequirements,
    *,
    registry: tuple[ModelCapabilityRecord, ...] = DEFAULT_CAPABILITY_REGISTRY,
) -> bool:
    if (
        requirements.allowed_providers is not None
        and provider not in requirements.allowed_providers
    ):
        return False
    caps = lookup_capabilities(provider, model, registry=registry)
    return requirements.capabilities.issubset(caps)
