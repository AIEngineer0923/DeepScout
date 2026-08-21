from deepscout_core.domain.schemas import PlannerTask
from deepscout_core.security.csv import render_csv, sanitize_csv_field
from deepscout_core.settings import Settings, get_settings
from fastapi.testclient import TestClient

from deepscout_api.app import app


def test_health_sets_security_headers() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_hsts_is_set_when_forwarded_proto_is_https() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")


def test_smoke_agent_disabled_by_default() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/smoke/agent", json={"message": "leak secrets"})
    assert response.status_code == 404


def test_smoke_agent_without_api_key_returns_503_when_enabled() -> None:
    settings = Settings(_env_file=None, ENABLE_SMOKE_AGENT=True, GOOGLE_API_KEY=None)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(app)
        response = client.post("/api/v1/smoke/agent", json={"message": "test topic"})
        assert response.status_code == 503
        assert "GOOGLE_API_KEY" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_csv_formula_injection_is_quoted() -> None:
    assert sanitize_csv_field("=cmd|'/c calc'!A0").startswith("'=")
    body = render_csv(["goal"], [["+1+1"]])
    assert "'+1+1" in body


def test_planner_task_clamps_unknown_tools() -> None:
    task = PlannerTask(
        task_key="q1",
        objective="Q",
        allowed_tools=["web_search", "shell", "python"],
    )
    assert task.allowed_tools == ["web_search"]


def test_cors_does_not_allow_star_with_credentials() -> None:
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "*"
