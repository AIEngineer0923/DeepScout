"""Model routing — capability-aware selection with optional configured fallback."""

from __future__ import annotations

from dataclasses import dataclass, replace

from deepscout_core.domain.enums import AgentRole
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_providers.config import ModelBuildOptions, options_from_settings
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS
from deepscout_providers.factory import build_chat_model
from deepscout_research.routing.capabilities import ModelRequirements, satisfies_requirements
from deepscout_research.routing.provider_health import (
    DEFAULT_PROVIDER_HEALTH,
    ProviderHealthRegistry,
)
from langchain_core.language_models.chat_models import BaseChatModel


@dataclass(frozen=True, slots=True)
class ModelSelection:
    provider: ProviderKind
    model: str
    agent_role: AgentRole
    fallback_provider: ProviderKind | None = None
    fallback_model: str | None = None
    reasoning_level: str | None = None
    used_fallback: bool = False
    fallback_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AgentModelPolicy:
    role: AgentRole
    provider: ProviderKind | None = None
    model: str | None = None
    fallback_provider: ProviderKind | None = None
    fallback_model: str | None = None
    reasoning_level: str | None = None


class IncompatibleFallbackError(ValueError):
    """Fallback candidate does not satisfy required capabilities or privacy allowlist."""


class ModelRouter:
    """Resolve model/provider by role + capabilities without leaking into domain logic."""

    def __init__(
        self,
        settings: Settings,
        policies: list[AgentModelPolicy] | None = None,
        *,
        health: ProviderHealthRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._policies = {policy.role: policy for policy in (policies or [])}
        self._health = health or DEFAULT_PROVIDER_HEALTH

    def resolve(
        self,
        role: AgentRole,
        *,
        requirements: ModelRequirements | None = None,
    ) -> ModelSelection:
        policy = self._policies.get(role)
        provider = policy.provider if policy and policy.provider else self._settings.llm_provider
        model = (
            policy.model
            if policy and policy.model
            else self._settings.llm_model or DEFAULT_CHAT_MODELS[provider]
        )
        if requirements is not None and not satisfies_requirements(provider, model, requirements):
            raise IncompatibleFallbackError(
                f"primary {provider.value}:{model} lacks required capabilities"
            )
        return ModelSelection(
            provider=provider,
            model=model,
            agent_role=role,
            fallback_provider=policy.fallback_provider if policy else None,
            fallback_model=policy.fallback_model if policy else None,
            reasoning_level=policy.reasoning_level if policy else None,
        )

    def select_with_fallback(
        self,
        role: AgentRole,
        *,
        requirements: ModelRequirements,
        prefer_fallback: bool = False,
        fallback_reason: str | None = None,
    ) -> ModelSelection:
        """Pick primary or capability-compatible fallback. Never silent capability downgrade."""
        primary = self.resolve(role, requirements=None)
        primary_ok = satisfies_requirements(primary.provider, primary.model, requirements)
        primary_healthy = self._health.is_available(primary.provider)

        if primary_ok and primary_healthy and not prefer_fallback:
            return primary

        if not requirements.fallback_allowed:
            if not primary_ok:
                raise IncompatibleFallbackError(
                    f"primary {primary.provider.value}:{primary.model} lacks capabilities"
                )
            if not primary_healthy or prefer_fallback:
                raise IncompatibleFallbackError("fallback not allowed by requirements")
            return primary

        policy = self._policies.get(role)
        if policy is None or policy.fallback_provider is None or policy.fallback_model is None:
            raise IncompatibleFallbackError("no configured fallback")

        fb_provider = policy.fallback_provider
        fb_model = policy.fallback_model
        allow = requirements.allowed_providers
        if allow is not None and fb_provider not in allow:
            raise IncompatibleFallbackError("fallback provider not in privacy allowlist")

        fb_req = replace(requirements, allowed_providers=None)
        if not satisfies_requirements(fb_provider, fb_model, fb_req):
            raise IncompatibleFallbackError("fallback lacks required capabilities")
        if not self._health.is_available(fb_provider):
            raise IncompatibleFallbackError("fallback provider marked unhealthy")

        return ModelSelection(
            provider=fb_provider,
            model=fb_model,
            agent_role=role,
            fallback_provider=None,
            fallback_model=None,
            reasoning_level=policy.reasoning_level,
            used_fallback=True,
            fallback_reason=fallback_reason or "primary_unavailable_or_unhealthy",
        )

    def build_chat_model(
        self,
        role: AgentRole,
        *,
        options: ModelBuildOptions | None = None,
        requirements: ModelRequirements | None = None,
        prefer_fallback: bool = False,
        fallback_reason: str | None = None,
    ) -> tuple[BaseChatModel, ModelSelection]:
        build_options = options or options_from_settings(self._settings)
        if requirements is not None and requirements.fallback_allowed:
            selection = self.select_with_fallback(
                role,
                requirements=requirements,
                prefer_fallback=prefer_fallback,
                fallback_reason=fallback_reason,
            )
        else:
            selection = self.resolve(role, requirements=requirements)
        model = build_chat_model(
            self._settings,
            options=build_options,
            provider=selection.provider,
            model_name=selection.model,
        )
        return model, selection
