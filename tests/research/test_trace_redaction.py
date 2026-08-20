"""Trace input redaction for LangSmith privacy."""

from deepscout_core.settings import Settings
from deepscout_research.trace_redaction import redact_trace_inputs


def test_redact_trace_inputs_strips_settings_and_urls() -> None:
    settings = Settings()
    redacted = redact_trace_inputs(
        {
            "run_id": "00000000-0000-0000-0000-000000000001",
            "goal": "Example goal",
            "budget_summary": "iterations=1",
            "settings": settings.model_dump(),
            "database_url": settings.database_url,
        }
    )

    assert redacted["goal"] == "Example goal"
    assert redacted["settings"] == "<redacted>"
    assert redacted["database_url"] == "<redacted>"
    assert settings.google_api_key is None or str(settings.google_api_key) not in str(redacted)
