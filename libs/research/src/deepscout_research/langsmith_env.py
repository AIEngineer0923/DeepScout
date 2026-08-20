"""Load LangSmith client environment from repository settings without logging secrets."""

from __future__ import annotations

import os

from deepscout_core.settings import Settings, get_settings


def configure_langsmith_env(settings: Settings | None = None) -> Settings:
    """Apply repository settings to process env for LangSmith SDK clients."""
    settings = settings or get_settings()
    if settings.langsmith_api_key is not None:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key.get_secret_value()
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    if settings.langsmith_workspace_id:
        os.environ["LANGSMITH_WORKSPACE_ID"] = settings.langsmith_workspace_id
    os.environ["LANGSMITH_TRACING"] = "true" if settings.langsmith_tracing else "false"
    return settings
