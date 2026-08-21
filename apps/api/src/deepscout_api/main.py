import os

from deepscout_core.settings import Settings, get_settings


def configure_observability(settings: Settings) -> None:
    """Apply LangSmith environment variables for LangChain auto-tracing."""
    os.environ["LANGSMITH_TRACING"] = "true" if settings.langsmith_tracing else "false"
    if settings.langsmith_project:
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_workspace_id:
        os.environ["LANGSMITH_WORKSPACE_ID"] = settings.langsmith_workspace_id
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    if settings.langsmith_tracing and settings.langsmith_api_key is not None:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key.get_secret_value()


def run() -> None:
    import uvicorn

    settings = get_settings()
    configure_observability(settings)
    port = int(os.environ.get("PORT") or settings.api_port)
    uvicorn.run(
        "deepscout_api.app:app",
        host=settings.api_host,
        port=port,
        reload=settings.app_debug,
        server_header=False,
    )
