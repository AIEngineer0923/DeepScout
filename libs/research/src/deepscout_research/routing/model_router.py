"""Model routing — provider-neutral role policies."""

from __future__ import annotations

from dataclasses import dataclass

from deepscout_core.domain.enums import AgentRole
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_providers.config import ModelBuildOptions
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS
from deepscout_providers.factory import build_chat_model
from langchain_core.language_models.chat_models import BaseChatModel


@dataclass(frozen=True, slots=True)
class ModelSelection:
    provider: ProviderKind
    model: str
    agent_role: AgentRole
    fallback_provider: ProviderKind | None = None
    fallback_model: str | None = None
    reasoning_level: str | None = None


@dataclass(frozen=True, slots=True)
class AgentModelPolicy:
    role: AgentRole
    provider: ProviderKind | None = None
    model: str | None = None
    fallback_provider: ProviderKind | None = None
    fallback_model: str | None = None
    reasoning_level: str | None = None


class ModelRouter:
    """Resolve model/provider by agent role without leaking into domain logic."""

    def __init__(self, settings: Settings, policies: list[AgentModelPolicy] | None = None) -> None:
        self._settings = settings
        self._policies = {policy.role: policy for policy in (policies or [])}

    def resolve(self, role: AgentRole) -> ModelSelection:
        policy = self._policies.get(role)
        provider = (
            policy.provider
            if policy and policy.provider
            else self._settings.llm_provider
        )
        model = (
            policy.model
            if policy and policy.model
            else self._settings.llm_model or DEFAULT_CHAT_MODELS[provider]
        )
        return ModelSelection(
            provider=provider,
            model=model,
            agent_role=role,
            fallback_provider=policy.fallback_provider if policy else None,
            fallback_model=policy.fallback_model if policy else None,
            reasoning_level=policy.reasoning_level if policy else None,
        )

    def build_chat_model(
        self,
        role: AgentRole,
        *,
        options: ModelBuildOptions | None = None,
    ) -> tuple[BaseChatModel, ModelSelection]:
        selection = self.resolve(role)
        model = build_chat_model(
            self._settings,
            options=options,
            provider=selection.provider,
            model_name=selection.model,
        )
        return model, selection
