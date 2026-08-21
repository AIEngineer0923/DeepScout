from deepscout_core.settings import Settings, get_settings
from deepscout_core.types import ProviderKind
from fastapi.testclient import TestClient

from deepscout_api.app import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_smoke_agent_without_api_key_returns_503() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER=ProviderKind.GOOGLE,
        GOOGLE_API_KEY=None,
        ENABLE_SMOKE_AGENT=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(app)
        response = client.post("/api/v1/smoke/agent", json={"message": "test topic"})
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()
