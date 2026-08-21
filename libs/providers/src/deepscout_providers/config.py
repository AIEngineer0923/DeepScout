"""Provider-neutral model construction options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deepscout_core.settings import Settings


@dataclass(frozen=True, slots=True)
class ModelBuildOptions:
    """Cross-provider options with stable semantics.

    Sampling parameters (temperature, thinking level, reasoning effort) are
    intentionally omitted — each provider applies its own defaults in the factory.
    """

    timeout: float | None = None
    max_retries: int | None = None


DEFAULT_MODEL_BUILD_OPTIONS = ModelBuildOptions(timeout=60.0, max_retries=3)


def options_from_settings(settings: Settings) -> ModelBuildOptions:
    """Wire Settings.LLM_TIMEOUT_S / LLM_MAX_RETRIES into LangChain build options."""
    return ModelBuildOptions(
        timeout=float(settings.llm_timeout_s),
        max_retries=int(settings.llm_max_retries),
    )
