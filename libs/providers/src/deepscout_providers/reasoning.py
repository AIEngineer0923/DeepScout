"""Capability-aware reasoning controls. Unsupported kwargs are never sent."""

from __future__ import annotations

from typing import Any

from deepscout_core.types import ProviderKind

ALLOWED_EFFORT = frozenset({"minimal", "low", "medium", "high"})

# Conservative allowlists from provider docs as of August 2026.
# gpt-4.1-mini is NOT in this set — do not send reasoning_effort to it.
GOOGLE_THINKING_LEVEL_MODELS = frozenset(
    {
        "gemini-3.7-flash",
        "gemini-3.7-pro",
    }
)
OPENAI_REASONING_EFFORT_PREFIXES = ("o1", "o3", "o4", "gpt-5")


def provider_reasoning_kwargs(
    provider: ProviderKind,
    model: str,
    effort: str | None,
) -> dict[str, Any]:
    """Return provider-specific kwargs, or {} if unset/unsupported."""
    if not effort:
        return {}
    normalized = effort.strip().lower()
    if normalized not in ALLOWED_EFFORT:
        return {}
    if provider == ProviderKind.GOOGLE and model in GOOGLE_THINKING_LEVEL_MODELS:
        return {"thinking_level": normalized}
    if provider == ProviderKind.OPENAI and model.startswith(OPENAI_REASONING_EFFORT_PREFIXES):
        return {"reasoning_effort": normalized}
    return {}
