"""Instrument nested-retry risk: application owns attempts; transport retries = 0."""

from __future__ import annotations

import httpx
from deepscout_core.domain.enums import AgentRole
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_providers.config import (
    PROVIDER_TRANSPORT_MAX_RETRIES,
    application_retry_policy,
    options_from_settings,
)
from deepscout_research.retry import RetryPolicy, run_with_retry
from deepscout_research.routing.capabilities import ModelCapability, ModelRequirements
from deepscout_research.routing.model_router import AgentModelPolicy, ModelRouter
from deepscout_research.routing.resilient_invoke import (
    invoke_with_resilience,
    max_effective_provider_attempts,
)


def _settings(retries: int = 3) -> Settings:
    return Settings(
        _env_file=None,
        LLM_PROVIDER=ProviderKind.GOOGLE,
        LLM_MODEL="gemini-3.7-flash",
        LLM_MAX_RETRIES=retries,
    )


def test_transport_retries_disabled_while_app_owns_logical_retries() -> None:
    settings = _settings(3)
    assert options_from_settings(settings).max_retries == PROVIDER_TRANSPORT_MAX_RETRIES == 0
    assert application_retry_policy(settings).max_attempts == 3


def test_connection_error_application_attempts_equal_real_adapter_calls() -> None:
    """With transport max_retries=0, each app attempt == one adapter call."""
    settings = _settings(3)
    adapter_calls = {"n": 0}

    def adapter() -> str:
        adapter_calls["n"] += 1
        raise ConnectionError("reset")

    try:
        run_with_retry(adapter, policy=application_retry_policy(settings))
    except ConnectionError:
        pass
    assert adapter_calls["n"] == 3
    # Nested risk if transport also retried 3x would be 9 — must not happen.
    assert max_effective_provider_attempts(llm_max_retries=3, fallback_allowed=False) == 3


def test_429_bounded_to_application_attempts() -> None:
    req = httpx.Request("POST", "https://provider.test/v1")
    calls = {"n": 0}

    def always_429() -> None:
        calls["n"] += 1
        raise httpx.HTTPStatusError(
            "rate",
            request=req,
            response=httpx.Response(429, request=req),
        )

    try:
        run_with_retry(
            always_429,
            policy=RetryPolicy(max_attempts=3, base_delay_s=0.01, jitter=False),
        )
    except httpx.HTTPStatusError:
        pass
    assert calls["n"] == 3


def test_timeout_and_503_bounded() -> None:
    settings = _settings(2)

    def run_case(exc: BaseException) -> int:
        calls = {"n": 0}

        def op() -> None:
            calls["n"] += 1
            raise exc

        try:
            run_with_retry(op, policy=application_retry_policy(settings))
        except Exception:
            pass
        return calls["n"]

    assert run_case(TimeoutError("deadline")) == 2
    req = httpx.Request("GET", "https://x")
    err_503 = httpx.HTTPStatusError(
        "bad",
        request=req,
        response=httpx.Response(503, request=req),
    )
    assert run_case(err_503) == 2


def test_fallback_path_max_attempts_documented() -> None:
    settings = _settings(2)
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
    calls: list[str] = []

    def op(selection):  # noqa: ANN001
        calls.append(selection.provider.value)
        raise ConnectionError("down")

    try:
        invoke_with_resilience(
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
            retry_policy=RetryPolicy(max_attempts=2, base_delay_s=0.01, jitter=False),
        )
    except ConnectionError:
        pass

    # Primary 2 + fallback 2 = 4; never 2 * 3 transport * 2 models.
    assert len(calls) == 4
    assert max_effective_provider_attempts(llm_max_retries=2, fallback_allowed=True) == 4
    assert calls.count("google") == 2
    assert calls.count("openai") == 2
