"""Provider-neutral model construction options."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelBuildOptions:
    """Cross-provider options with stable semantics.

    Sampling parameters (temperature, thinking level, reasoning effort) are
    intentionally omitted — each provider applies its own defaults in the factory.
    """

    timeout: float | None = None
    max_retries: int | None = None


DEFAULT_MODEL_BUILD_OPTIONS = ModelBuildOptions(timeout=60.0, max_retries=3)
