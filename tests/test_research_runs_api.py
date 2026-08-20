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
