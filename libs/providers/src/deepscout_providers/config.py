"""Provider-neutral model construction options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deepscout_core.settings import Settings
    from deepscout_research.retry import RetryPolicy

# Provider/LangChain SDK transport retries are disabled by default.
# Application code owns logical retries via Settings.LLM_MAX_RETRIES + run_with_retry.
# Google HttpRetryOptions: attempts 0 or 1 means no retries.
# OpenAI/Anthropic: max_retries=0 disables client retries.
PROVIDER_TRANSPORT_MAX_RETRIES = 0


@dataclass(frozen=True, slots=True)
class ModelBuildOptions:
    """Cross-provider options with stable semantics.

    Sampling parameters (temperature, thinking level, reasoning effort) are
    intentionally omitted — each provider applies its own defaults in the factory.
    """

    timeout: float | None = None
    max_retries: int | None = None


DEFAULT_MODEL_BUILD_OPTIONS = ModelBuildOptions(
    timeout=60.0,
    max_retries=PROVIDER_TRANSPORT_MAX_RETRIES,
)


def options_from_settings(settings: Settings) -> ModelBuildOptions:
    """Wire timeout from Settings; keep provider transport retries at zero.

    ``LLM_MAX_RETRIES`` is NOT passed to LangChain — it feeds application
    ``RetryPolicy`` only (see ``application_retry_policy``).
    """
    return ModelBuildOptions(
        timeout=float(settings.llm_timeout_s),
        max_retries=PROVIDER_TRANSPORT_MAX_RETRIES,
    )


def application_retry_policy(settings: Settings) -> RetryPolicy:
    """Single logical retry authority for one model/search invocation."""
    from deepscout_research.retry import RetryPolicy

    return RetryPolicy(max_attempts=max(1, int(settings.llm_max_retries)))
