#!/usr/bin/env python3
"""Bounded live agent-runtime matrix. Skips honestly when credentials are absent."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from deepscout_core.settings import get_settings
from deepscout_research.langsmith_env import configure_langsmith_env


def main() -> int:
    settings = get_settings()
    has_llm = settings.google_api_key is not None or settings.openai_api_key is not None or (
        settings.anthropic_api_key is not None
    )
    has_search = settings.tavily_api_key is not None
    has_langsmith = settings.langsmith_api_key is not None
    if has_langsmith:
        configure_langsmith_env(settings)

    if not has_llm or not has_search:
        print(
            json.dumps(
                {
                    "status": "SKIPPED",
                    "reason": "live_credentials_absent",
                    "llm_configured": has_llm,
                    "tavily_configured": has_search,
                    "langsmith_configured": has_langsmith,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "note": (
                        "Structural benchmark remains authoritative. "
                        "Do not invent live quality/cost winners."
                    ),
                },
                indent=2,
            )
        )
        return 0

    print(
        json.dumps(
            {
                "status": "READY",
                "note": (
                    "Credentials present. Prefer the smallest orchestrator live tests "
                    "already in tests/test_orchestrator_live.py rather than repeating "
                    "unbounded spend here."
                ),
                "llm_provider": settings.llm_provider.value,
                "langsmith_tracing": settings.langsmith_tracing,
                "langsmith_configured": has_langsmith,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
