"""Output safety tests that do not depend on the Next.js tree."""

from fastapi.testclient import TestClient

from deepscout_api.app import app


def test_create_rejects_oversized_goal() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/research-runs", json={"goal": "x" * 9000})
    assert response.status_code == 422
