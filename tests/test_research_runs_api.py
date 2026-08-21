import uuid
from collections.abc import Generator

import pytest
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
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def validation_client() -> TestClient:
    return TestClient(app)


@pytest.mark.postgres
def test_create_and_get_research_run(api_client: TestClient) -> None:
    create = api_client.post(
        "/api/v1/research-runs",
        json={"goal": "Compare EV battery chemistries"},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["goal"] == "Compare EV battery chemistries"
    assert body["llm_model"] == "gemini-3.7-flash"

    run_id = body["id"]
    get = api_client.get(f"/api/v1/research-runs/{run_id}")
    assert get.status_code == 200
    assert get.json()["id"] == run_id

    summary = api_client.get(f"/api/v1/research-runs/{run_id}/summary")
    assert summary.status_code == 200
    summary_body = summary.json()
    assert summary_body["run_id"] == run_id
    assert summary_body["claim_count"] == 0


@pytest.mark.postgres
def test_cancel_research_run(api_client: TestClient) -> None:
    create = api_client.post(
        "/api/v1/research-runs",
        json={"goal": "Cancel test"},
    )
    run_id = create.json()["id"]
    cancel = api_client.post(f"/api/v1/research-runs/{run_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"
    events = api_client.get(f"/api/v1/research-runs/{run_id}/events")
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "id:" in events.text or events.text == ""


@pytest.mark.postgres
def test_sse_replay_uses_after_query(api_client: TestClient) -> None:
    create = api_client.post("/api/v1/research-runs", json={"goal": "SSE replay"})
    run_id = create.json()["id"]
    api_client.post(f"/api/v1/research-runs/{run_id}/cancel")
    replay = api_client.get(f"/api/v1/research-runs/{run_id}/events?after=999999")
    assert replay.status_code == 200
    assert replay.text == "" or ": keepalive" in replay.text or "id:" in replay.text

@pytest.mark.postgres
def test_get_unknown_run_returns_404(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/research-runs/{uuid.uuid4()}")
    assert response.status_code == 404


def test_invalid_uuid_returns_422(validation_client: TestClient) -> None:
    response = validation_client.get("/api/v1/research-runs/not-a-uuid")
    assert response.status_code == 422


def test_oversized_goal_is_rejected(validation_client: TestClient) -> None:
    response = validation_client.post("/api/v1/research-runs", json={"goal": "x" * 9000})
    assert response.status_code == 422


def test_empty_goal_is_rejected(validation_client: TestClient) -> None:
    response = validation_client.post("/api/v1/research-runs", json={"goal": ""})
    assert response.status_code == 422


@pytest.mark.postgres
def test_list_and_overview(api_client: TestClient) -> None:
    created = api_client.post("/api/v1/research-runs", json={"goal": "List overview research"})
    run_id = created.json()["id"]
    listed = api_client.get("/api/v1/research-runs")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    overview = api_client.get("/api/v1/overview")
    assert overview.status_code == 200
    settings = api_client.get("/api/v1/settings")
    assert settings.status_code == 200
    assert "google" in settings.json()["providers"]
    workspace = api_client.get(f"/api/v1/research-runs/{run_id}/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["goal"] == "List overview research"
    export = api_client.get(f"/api/v1/research-runs/{run_id}/export?format=markdown")
    assert export.status_code == 200


@pytest.mark.postgres
def test_create_run_persists_mode_and_language(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/research-runs",
        json={"goal": "Deep mode Italian report", "research_mode": "deep", "output_language": "it"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["research_mode"] == "deep"
    assert body["output_language"] == "it"
    workspace = api_client.get(f"/api/v1/research-runs/{body['id']}/workspace")
    assert workspace.json()["research_mode"] == "deep"
    assert workspace.json()["output_language"] == "it"


@pytest.mark.postgres
def test_resume_cancelled_run_conflict(api_client: TestClient) -> None:
    created = api_client.post("/api/v1/research-runs", json={"goal": "Resume guard"})
    run_id = created.json()["id"]
    cancel = api_client.post(f"/api/v1/research-runs/{run_id}/cancel")
    assert cancel.status_code == 200
    response = api_client.post(f"/api/v1/research-runs/{run_id}/resume")
    assert response.status_code == 409


@pytest.mark.postgres
def test_research_templates_crud(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/research-templates",
        json={
            "name": "EU AI Act",
            "goal": "Summarize obligations for a SaaS vendor",
            "research_mode": "standard",
            "output_language": "en",
        },
    )
    assert created.status_code == 201
    template_id = created.json()["id"]
    listed = api_client.get("/api/v1/research-templates")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "EU AI Act"
    deleted = api_client.delete(f"/api/v1/research-templates/{template_id}")
    assert deleted.status_code == 204
    assert api_client.get("/api/v1/research-templates").json() == []
