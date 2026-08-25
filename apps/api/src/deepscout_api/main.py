import os

from deepscout_core.settings import Settings, get_settings
from deepscout_research.credentials.runtime import configure_process_observability


def configure_observability(settings: Settings) -> None:
    """Apply the safe process baseline; hosted run credentials are installed per job."""
    configure_process_observability(settings)


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
