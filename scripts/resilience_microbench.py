#!/usr/bin/env python3
"""Small local resilience micro-benchmark (not an SLO claim)."""

from __future__ import annotations

import time

from deepscout_core.domain.enums import AgentRole
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_research.retry import RetryPolicy, run_with_retry
from deepscout_research.routing.capabilities import ModelCapability, ModelRequirements
from deepscout_research.routing.model_router import AgentModelPolicy, ModelRouter
from deepscout_research.routing.provider_health import ProviderHealthRegistry
from deepscout_research.routing.resilient_invoke import invoke_with_resilience


def main() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER=ProviderKind.GOOGLE,
        LLM_MODEL="gemini-3.7-flash",
        LLM_MAX_RETRIES=2,
    )
    health = ProviderHealthRegistry(failure_threshold=99)
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
    req = ModelRequirements(
        capabilities=frozenset(
            {
                ModelCapability.CHAT,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.TOOL_CALLING,
            }
        ),
        allowed_providers=frozenset({ProviderKind.GOOGLE, ProviderKind.OPENAI}),
        fallback_allowed=True,
    )

    t0 = time.perf_counter()
    run_with_retry(lambda: "ok", policy=RetryPolicy(max_attempts=1))
    normal_ms = (time.perf_counter() - t0) * 1000

    def fail_then_ok(selection):  # noqa: ANN001
        if selection.provider == ProviderKind.GOOGLE:
            raise ConnectionError("down")
        return "ok"

    t1 = time.perf_counter()
    result = invoke_with_resilience(
        settings=settings,
        role=AgentRole.PLANNER,
        operation=fail_then_ok,
        requirements=req,
        router=router,
        health=health,
        retry_policy=RetryPolicy(max_attempts=2, base_delay_s=0.01, jitter=False),
    )
    fallback_ms = (time.perf_counter() - t1) * 1000

    print(
        {
            "normal_ms": round(normal_ms, 3),
            "fallback_ms": round(fallback_ms, 3),
            "used_fallback": result.selection.used_fallback,
            "provider": result.selection.provider.value,
            "attempts": result.attempts,
            "note": "local microbench — not a production SLO",
        }
    )


if __name__ == "__main__":
    main()
