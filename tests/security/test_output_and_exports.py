"""Output safety tests that do not depend on the Next.js tree."""

from deepscout_evaluation.security_evals import eval_pii_leakage_texts
from fastapi.testclient import TestClient

from deepscout_api.app import app


def test_create_rejects_oversized_goal() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/research-runs", json={"goal": "x" * 9000})
    assert response.status_code == 422


def test_pii_evaluator_ignores_public_url_path_ids_but_scans_query_values() -> None:
    assert eval_pii_leakage_texts(
        ["[Article](https://example.org/research/1234567890123456)"]
    )
    assert not eval_pii_leakage_texts(
        ["https://example.org/search?account=1234567890123456"]
    )
