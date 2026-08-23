"""Hosted tenant isolation — UUID secrecy is not authorization."""

from __future__ import annotations

from uuid import uuid4

import pytest
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings
from deepscout_persistence.identity import create_session, upsert_oauth_principal
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from fastapi.testclient import TestClient
from tests.db_helpers import database_url

pytestmark = pytest.mark.postgres


@pytest.fixture
def hosted_client(monkeypatch, postgres_ready):
    monkeypatch.setenv("DEEPSCOUT_DEPLOYMENT_MODE", "hosted")
    monkeypatch.setenv("SESSION_SECRET", "session-secret-for-tests-not-used-directly")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "0" * 32)
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "test-github-id")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "test-github-secret")
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "1000")
    monkeypatch.setenv("RATE_LIMIT_MUTATING_MAX", "1000")
    from deepscout_api.app import app

    return TestClient(app)


def _session():
    return get_session_factory(database_url())()


def _user(session, name: str):
    principal = upsert_oauth_principal(
        session,
        provider="github",
        provider_account_id=f"{name}-{uuid4().hex[:8]}",
        display_name=name,
        email=None,
        email_verified=False,
        avatar_url=None,
    )
    token = create_session(session, principal.id)
    session.commit()
    return principal, token


def test_user_b_cannot_read_user_a_run(hosted_client) -> None:
    session = _session()
    store = ResearchStore(session)
    settings = Settings(_env_file=None)
    user_a, token_a = _user(session, "A")
    user_b, token_b = _user(session, "B")
    run = store.create_run(
        ResearchRunCreate(goal="User A private research"),
        settings,
        owner_principal_id=user_a.id,
    )
    session.commit()
    try:
        denied = hosted_client.get(
            f"/api/v1/research-runs/{run.id}", cookies={"ds_session": token_b}
        )
        assert denied.status_code == 404
        allowed = hosted_client.get(
            f"/api/v1/research-runs/{run.id}", cookies={"ds_session": token_a}
        )
        assert allowed.status_code == 200
        assert hosted_client.get(f"/api/v1/research-runs/{run.id}").status_code == 404
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, user_a.id)
        delete_principal_data(session, user_b.id)
        session.commit()
        session.close()


def test_demo_is_read_only_for_anonymous(hosted_client) -> None:
    session = _session()
    store = ResearchStore(session)
    settings = Settings(_env_file=None)
    user_a, _token = _user(session, "DemoOwner")
    demo = store.create_run(
        ResearchRunCreate(goal="Published demo"),
        settings,
        owner_principal_id=user_a.id,
        is_public_demo=True,
        public_slug=f"demo-{uuid4().hex[:8]}",
    )
    session.commit()
    try:
        assert hosted_client.get(f"/api/v1/research-runs/{demo.id}").status_code == 200
        execute = hosted_client.post(f"/api/v1/research-runs/{demo.id}/execute")
        assert execute.status_code in {401, 403, 404}
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, user_a.id)
        session.commit()
        session.close()


def test_open_redirect_rejected() -> None:
    from deepscout_api.access import safe_next_path

    assert safe_next_path("https://evil.test", "/") == "/"
    assert safe_next_path("//evil.test", "/") == "/"
    assert safe_next_path("/account", "/,/account") == "/account"


def test_user_b_cannot_mutate_or_export_user_a(hosted_client) -> None:
    session = _session()
    store = ResearchStore(session)
    settings = Settings(_env_file=None)
    user_a, token_a = _user(session, "A")
    user_b, token_b = _user(session, "B")
    run = store.create_run(
        ResearchRunCreate(goal="User A private research"),
        settings,
        owner_principal_id=user_a.id,
    )
    session.commit()
    cookies_b = {"ds_session": token_b}
    cookies_a = {"ds_session": token_a}
    try:
        paths = [
            ("get", f"/api/v1/research-runs/{run.id}/export?format=markdown", None),
            ("get", f"/api/v1/research-runs/{run.id}/evaluations", None),
            ("get", f"/api/v1/research-runs/{run.id}/workspace", None),
            ("get", f"/api/v1/research-runs/{run.id}/events", None),
            ("get", f"/api/v1/knowledge/search?run_id={run.id}&q=test", None),
            ("get", f"/api/v1/knowledge/graph?run_id={run.id}", None),
            ("post", f"/api/v1/research-runs/{run.id}/cancel", None),
            ("post", f"/api/v1/research-runs/{run.id}/resume", None),
            ("post", f"/api/v1/research-runs/{run.id}/restart", None),
            ("post", f"/api/v1/research-runs/{run.id}/fork", {"reason": "stolen"}),
            ("post", f"/api/v1/research-runs/{run.id}/execute", None),
        ]
        for method, path, body in paths:
            kwargs: dict = {"cookies": cookies_b}
            if body is not None:
                kwargs["json"] = body
            response = getattr(hosted_client, method)(path, **kwargs)
            assert response.status_code == 404, path
        assert (
            hosted_client.get(
                f"/api/v1/research-runs/{run.id}/export?format=json", cookies=cookies_a
            ).status_code
            == 200
        )
        export = hosted_client.get("/api/v1/account/export", cookies=cookies_a)
        assert export.status_code == 200
        assert "ciphertext" not in export.text
        assert "secret" not in export.text.lower() or "SecretStr" not in export.text
        settings_payload = hosted_client.get("/api/v1/settings").json()
        assert settings_payload["langsmith"]["tracing"] is False
        assert settings_payload["langsmith"]["connected"] is False
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, user_a.id)
        delete_principal_data(session, user_b.id)
        session.commit()
        session.close()


def test_mismatched_origin_is_rejected(hosted_client) -> None:
    denied = hosted_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "https://evil.example"},
    )
    assert denied.status_code == 403


def test_learning_candidate_decisions_are_owner_scoped(hosted_client) -> None:
    session = _session()
    store = ResearchStore(session)
    user_a, token_a = _user(session, "LearningOwnerA")
    user_b, token_b = _user(session, "LearningOwnerB")
    case_id = store.upsert_learning_case(
        {
            "case_key": f"tenant-case-{uuid4().hex}",
            "owner_principal_id": user_a.id,
            "subsystem": "retrieval",
            "failure_class": "retrieval_failure",
            "symptom": "owner-scoped candidate",
            "origin": "development_synthetic",
            "trust_level": "validated_learning",
            "review_state": "diagnosed",
            "sanitized": True,
        }
    )
    candidate_id = store.upsert_improvement_candidate(
        {
            "candidate_key": f"tenant-candidate-{uuid4().hex}",
            "learning_case_row_id": case_id,
            "owner_principal_id": user_a.id,
            "candidate_type": "retrieval_parameter",
            "title": "Scoped candidate",
            "rationale": "Regression coverage",
            "affected_subsystem": "retrieval",
            "trust_level": "validated_learning",
            "status": "requires_human_review",
        }
    )
    session.commit()
    try:
        denied = hosted_client.post(
            f"/api/v1/learning/candidates/{candidate_id}/approve",
            json={},
            cookies={"ds_session": token_b},
        )
        assert denied.status_code == 404
        allowed = hosted_client.post(
            f"/api/v1/learning/candidates/{candidate_id}/approve",
            json={},
            cookies={"ds_session": token_a},
        )
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "approved"
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, user_a.id)
        delete_principal_data(session, user_b.id)
        session.commit()
        session.close()


def test_controlled_learning_smoke_is_not_available_to_regular_hosted_users(
    hosted_client,
) -> None:
    session = _session()
    user, token = _user(session, "RegularHostedUser")
    try:
        response = hosted_client.post(
            "/api/v1/learning/smoke/controlled",
            cookies={"ds_session": token},
        )
        assert response.status_code == 404
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, user.id)
        session.commit()
        session.close()
