"""Bounded DAST-style tests against the local FastAPI application only."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from deepscout_core.settings import Settings, get_settings
from deepscout_persistence.session import get_session_factory
from fastapi.testclient import TestClient
from tests.db_helpers import database_url, postgres_available

from deepscout_api.app import app
from deepscout_api.deps import get_db


@pytest.fixture
def api_client() -> Generator[TestClient, None, None]:
    if not postgres_available():
        pytest.skip("PostgreSQL is not available for API persistence tests")
    session = get_session_factory(database_url())()
    settings = Settings(_env_file=None, APP_ENV="production", DATABASE_URL=database_url())

    def override_db():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_malformed_uuid_and_methods() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/research-runs/not-a-uuid").status_code == 422
    assert client.put("/health").status_code == 405
    assert client.delete("/health").status_code == 405


def test_invalid_pagination_and_enum() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/research-runs?limit=1000").status_code == 422
    assert client.get("/api/v1/research-runs?offset=-1").status_code == 422
    created = client.post(
        "/api/v1/research-runs",
        json={"goal": "enum check", "research_mode": "unlimited"},
    )
    assert created.status_code in {422, 400}


def test_unexpected_json_types_and_missing_fields() -> None:
    client = TestClient(app)
    assert client.post("/api/v1/research-runs", json={"goal": 12}).status_code == 422
    assert client.post("/api/v1/research-runs", json={}).status_code == 422
    assert client.post("/api/v1/research-runs", content="not-json").status_code == 422


def test_oversized_request_body_is_rejected() -> None:
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route

    from deepscout_api.security import BodySizeLimitMiddleware

    async def _ok(_request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    probe = Starlette(routes=[Route("/submit", _ok, methods=["POST"])])
    probe.add_middleware(BodySizeLimitMiddleware, max_bytes=64)
    client = TestClient(probe)
    assert client.post("/submit", content=b"x" * 8).status_code == 200
    assert client.post("/submit", content=b"x" * 200).status_code == 413


def test_cors_and_docs_are_closed() -> None:
    client = TestClient(app)
    options = client.options(
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert options.headers.get("access-control-allow-origin") != "*"
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


@pytest.mark.postgres
def test_repeated_execute_resume_cancel_restart(api_client: TestClient) -> None:
    created = api_client.post("/api/v1/research-runs", json={"goal": "DAST execute race"})
    run_id = created.json()["id"]
    first = api_client.post(f"/api/v1/research-runs/{run_id}/execute")
    second = api_client.post(f"/api/v1/research-runs/{run_id}/execute")
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]

    resume_a = api_client.post(f"/api/v1/research-runs/{run_id}/resume")
    resume_b = api_client.post(f"/api/v1/research-runs/{run_id}/resume")
    assert resume_a.status_code == 202
    assert resume_b.status_code == 202
    assert resume_a.json()["job_id"] == resume_b.json()["job_id"]

    cancel = api_client.post(f"/api/v1/research-runs/{run_id}/cancel")
    assert cancel.status_code == 200
    assert api_client.post(f"/api/v1/research-runs/{run_id}/resume").status_code == 409

    restart = api_client.post(f"/api/v1/research-runs/{run_id}/restart")
    assert restart.status_code == 202
    assert restart.json()["run_id"] != run_id


@pytest.mark.postgres
def test_export_and_source_surfaces(api_client: TestClient) -> None:
    payload = {
        "goal": "=cmd|'/c calc'!A0 <script>alert(1)</script> javascript:alert(1)"
    }
    created = api_client.post("/api/v1/research-runs", json=payload)
    run_id = created.json()["id"]
    api_client.post(f"/api/v1/research-runs/{run_id}/cancel")
    listed = api_client.get("/api/v1/research-runs?format=csv")
    assert listed.status_code == 200
    assert "'=cmd|" in listed.text
    assert listed.headers["content-type"].startswith("text/csv")

    markdown = api_client.get(f"/api/v1/research-runs/{run_id}/export?format=markdown")
    assert markdown.status_code == 200
    json_export = api_client.get(f"/api/v1/research-runs/{run_id}/export?format=json")
    assert json_export.status_code == 200
    assert json_export.headers["content-type"].startswith("application/json")
    assert json_export.json()["goal"].startswith("=")
    for fmt in ("csv", "pdf", "evals-json", "evals-csv"):
        exported = api_client.get(f"/api/v1/research-runs/{run_id}/export?format={fmt}")
        assert exported.status_code == 200
    assert api_client.get(f"/api/v1/research-runs/{run_id}/export?format=nope").status_code == 422
    evals = api_client.get(f"/api/v1/research-runs/{run_id}/evaluations")
    assert evals.status_code == 200
    snapshot = api_client.get(f"/api/v1/research-runs/{run_id}/snapshots/{run_id}")
    assert snapshot.status_code == 404
    events = api_client.get(f"/api/v1/research-runs/{run_id}/events")
    assert events.status_code == 200
    assert events.headers.get("x-accel-buffering") == "no"


@pytest.mark.postgres
def test_idor_is_capability_url_without_auth(api_client: TestClient) -> None:
    first = api_client.post("/api/v1/research-runs", json={"goal": "operator A run"})
    second = api_client.post("/api/v1/research-runs", json={"goal": "operator B run"})
    a_id = first.json()["id"]
    b_id = second.json()["id"]
    stolen = api_client.get(f"/api/v1/research-runs/{a_id}")
    assert stolen.status_code == 200
    assert stolen.json()["id"] == a_id
    other = api_client.get(f"/api/v1/research-runs/{b_id}")
    assert other.status_code == 200
    cancel_other = api_client.post(f"/api/v1/research-runs/{b_id}/cancel")
    assert cancel_other.status_code == 200
