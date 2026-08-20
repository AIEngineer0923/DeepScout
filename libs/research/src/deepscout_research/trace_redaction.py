"""Redact sensitive values from LangSmith trace inputs."""

from __future__ import annotations

from typing import Any

_REDACTED = "<redacted>"
_SENSITIVE_KEYS = frozenset(
    {
        "settings",
        "database_url",
        "redis_url",
        "google_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "tavily_api_key",
        "langsmith_api_key",
    }
)


def redact_trace_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Remove secrets and settings blobs from traced function inputs."""
    redacted: dict[str, Any] = {}
    for key, value in inputs.items():
        if key in _SENSITIVE_KEYS:
            redacted[key] = _REDACTED
        elif isinstance(value, dict):
            redacted[key] = {
                nested_key: (_REDACTED if nested_key in _SENSITIVE_KEYS else nested_value)
                for nested_key, nested_value in value.items()
            }
        else:
            redacted[key] = value
    return redacted
