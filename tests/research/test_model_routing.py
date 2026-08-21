"""Capability-aware routing, privacy allowlists, and fallback safety."""

from deepscout_core.domain.enums import AgentRole
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_research.routing.capabilities import (
    ModelCapability,
    ModelRequirements,
    satisfies_requirements,
)
from deepscout_research.routing.model_router import (
    AgentModelPolicy,
    IncompatibleFallbackError,
    ModelRouter,
)
from deepscout_research.routing.provider_health import ProviderHealthRegistry
from deepscout_research.routing.resilient_invoke import invoke_with_resilience


def _settings(**kwargs: object) -> Settings:
    return Settings(
        _env_file=None,
        LLM_PROVIDER=ProviderKind.GOOGLE,
        LLM_MODEL="gemini-3.7-flash",
        LLM_TIMEOUT_S=12.0,
        LLM_MAX_RETRIES=2,
        **kwargs,  # type: ignore[arg-type]
    )


def test_options_from_settings_wires_timeout() -> None:
    from deepscout_providers.config import options_from_settings

    opts = options_from_settings(_settings())
    assert opts.timeout == 12.0
    assert opts.max_retries == 2


def test_capability_filter_rejects_embedding_as_chat() -> None:
    req = ModelRequirements(
        capabilities=frozenset(
            {ModelCapability.CHAT, ModelCapability.STRUCTURED_OUTPUT}
        )
    )
    assert (
        satisfies_requirements(
            ProviderKind.GOOGLE, "gemini-embedding-2", req
        )
        is False
    )


def test_privacy_allowlist_blocks_fallback_provider() -> None:
    settings = _settings()
    router = ModelRouter(
        settings,
        [
            AgentModelPolicy(
                role=AgentRole.PLANNER,
                provider=ProviderKind.GOOGLE,
                model="gemini-3.7-flash",
                fallback_provider=ProviderKind.OPENAI,
                fallback_model="gpt-4.1-mini",
            )
        ],
    )
    req = ModelRequirements(
        capabilities=frozenset(
            {
                ModelCapability.CHAT,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.TOOL_CALLING,
            }
        ),
        allowed_providers=frozenset({ProviderKind.GOOGLE}),
        fallback_allowed=True,
    )
    try:
        router.select_with_fallback(
            AgentRole.PLANNER, requirements=req, prefer_fallback=True
        )
        raise AssertionError("expected privacy block")
    except IncompatibleFallbackError as exc:
        assert "privacy" in str(exc).lower() or "allowlist" in str(exc).lower()


def test_fallback_requires_matching_capabilities() -> None:
    settings = _settings()
    # Point fallback at an embedding model id — must fail capability check.
    router = ModelRouter(
        settings,
        [
            AgentModelPolicy(
                role=AgentRole.PLANNER,
                provider=ProviderKind.GOOGLE,
                model="gemini-3.7-flash",
                fallback_provider=ProviderKind.GOOGLE,
                fallback_model="gemini-embedding-2",
            )
        ],
    )
    req = ModelRequirements(
        capabilities=frozenset(
            {
                ModelCapability.CHAT,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.TOOL_CALLING,
            }
        ),
        fallback_allowed=True,
    )
    try:
        router.select_with_fallback(
            AgentRole.PLANNER, requirements=req, prefer_fallback=True
        )
        raise AssertionError("expected capability failure")
    except IncompatibleFallbackError:
        pass


def test_resilient_invoke_falls_back_after_transient_failure() -> None:
    settings = _settings()
    health = ProviderHealthRegistry(failure_threshold=99, cooldown_s=1.0)
    router = ModelRouter(
        settings,
        [
            AgentModelPolicy(
                role=AgentRole.PLANNER,
                provider=ProviderKind.GOOGLE,
                model="gemini-3.7-flash",
                fallback_provider=ProviderKind.OPENAI,
                fallback_model="gpt-4.1-mini",
            )
        ],
        health=health,
    )
    calls: list[str] = []

    def op(selection):  # noqa: ANN001
        calls.append(f"{selection.provider.value}:{selection.model}")
        if selection.provider == ProviderKind.GOOGLE:
            raise ConnectionError("google down")
        return "ok"

    result = invoke_with_resilience(
        settings=settings,
        role=AgentRole.PLANNER,
        operation=op,
        requirements=ModelRequirements(
            capabilities=frozenset(
                {
                    ModelCapability.CHAT,
                    ModelCapability.STRUCTURED_OUTPUT,
                    ModelCapability.TOOL_CALLING,
                }
            ),
            allowed_providers=frozenset({ProviderKind.GOOGLE, ProviderKind.OPENAI}),
            fallback_allowed=True,
        ),
        router=router,
        health=health,
    )
    assert result.value == "ok"
    assert result.selection.used_fallback is True
    assert result.selection.provider == ProviderKind.OPENAI
    assert any(c.startswith("google:") for c in calls)
    assert any(c.startswith("openai:") for c in calls)


def test_provider_health_opens_after_threshold() -> None:
    health = ProviderHealthRegistry(failure_threshold=2, cooldown_s=60.0)
    assert health.is_available(ProviderKind.GOOGLE)
    health.record_failure(ProviderKind.GOOGLE, reason="timeout")
    assert health.is_available(ProviderKind.GOOGLE)
    health.record_failure(ProviderKind.GOOGLE, reason="timeout")
    assert health.is_available(ProviderKind.GOOGLE) is False
