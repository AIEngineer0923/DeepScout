from deepscout_core.settings import Settings
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from deepscout_api.security import RateLimitMiddleware


async def _ok(_request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def test_rate_limit_blocks_mutating_burst() -> None:
    settings = Settings(
        _env_file=None,
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_MUTATING_MAX=2,
        RATE_LIMIT_MAX_REQUESTS=100,
        RATE_LIMIT_WINDOW_S=60,
    )
    app = Starlette(routes=[Route("/api/v1/research-runs", _ok, methods=["POST"])])
    app.add_middleware(RateLimitMiddleware, settings=settings)
    client = TestClient(app)
    assert client.post("/api/v1/research-runs").status_code == 200
    assert client.post("/api/v1/research-runs").status_code == 200
    assert client.post("/api/v1/research-runs").status_code == 429
