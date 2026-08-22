"""Provider health recovery and readiness/liveness dependency policy."""

from __future__ import annotations

from unittest.mock import patch

from deepscout_core.settings import Settings, get_settings
from deepscout_core.types import ProviderKind
from deepscout_research.routing.provider_health import ProviderHealthRegistry
from fastapi.testclient import TestClient

from deepscout_api.app import app


def test_provider_health_recovers_after_cooldown() -> None:
    health = ProviderHealthRegistry(failure_threshold=2, cooldown_s=0.01)
    health.record_failure(ProviderKind.GOOGLE, reason="t1")
    health.record_failure(ProviderKind.GOOGLE, reason="t2")
    assert health.is_available(ProviderKind.GOOGLE) is False
    import time

    time.sleep(0.02)
    assert health.is_available(ProviderKind.GOOGLE) is True
    health.record_success(ProviderKind.OPENAI)
    # Keys bounded to ProviderKind enum values only.
    assert set(health._states.keys()).issubset(set(ProviderKind))


def test_live_ok_when_optional_deps_down() -> None:
    client = TestClient(app)
    assert client.get("/live").status_code == 200
    assert client.get("/health").status_code == 200


def test_ready_requires_postgres_not_redis_or_langsmith() -> None:
    settings = Settings(_env_file=None)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with (
            patch("deepscout_api.app.probe_postgres", return_value="unavailable"),
            patch("deepscout_api.app.probe_redis", return_value="unavailable"),
        ):
            client = TestClient(app)
            ready = client.get("/ready")
            assert ready.status_code == 503
            assert ready.json()["postgres"] == "unavailable"

        with (
            patch("deepscout_api.app.probe_postgres", return_value="ok"),
            patch("deepscout_api.app.probe_redis", return_value="unavailable"),
        ):
            client = TestClient(app)
            ready = client.get("/ready")
            assert ready.status_code == 200
            assert ready.json() == {"status": "ok", "postgres": "ok"}

        deps = TestClient(app).get("/api/v1/health/deps")
        # Redis probe may be unavailable; must not be required.
        body = deps.json()
        assert body["redis_required"] is False
    finally:
        app.dependency_overrides.clear()


def test_ready_hosted_fails_closed_without_auth() -> None:
    from deepscout_core.deployment import DeploymentMode

    settings = Settings(_env_file=None, DEEPSCOUT_DEPLOYMENT_MODE=DeploymentMode.HOSTED)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with patch("deepscout_api.app.probe_postgres", return_value="ok"):
            with patch("deepscout_api.app.probe_postgres_schema", return_value="ok"):
                client = TestClient(app)
                ready = client.get("/ready")
                assert ready.status_code == 503
                assert ready.json() == {"status": "unavailable", "postgres": "ok"}
            live = client.get("/live")
            assert live.status_code == 200
    finally:
        app.dependency_overrides.clear()
