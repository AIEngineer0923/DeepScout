"""Regression: mutation authz runs before request-body validation on demo runs."""

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


def _demo_and_private(hosted_client):
    session = _session()
    store = ResearchStore(session)
    settings = Settings(_env_file=None)
    owner, _token = _user(session, "DemoOwner")
    demo = store.create_run(
        ResearchRunCreate(goal="Published demo"),
        settings,
        owner_principal_id=owner.id,
        is_public_demo=True,
        public_slug=f"demo-{uuid4().hex[:8]}",
    )
    private = store.create_run(
        ResearchRunCreate(goal="Private research"),
        settings,
        owner_principal_id=owner.id,
    )
    session.commit()
    return session, store, owner, demo, private


def test_anonymous_demo_follow_up_malformed_body_is_forbidden_not_422(hosted_client) -> None:
    session, store, owner, demo, private = _demo_and_private(hosted_client)
    try:
        response = hosted_client.post(f"/api/v1/research-runs/{demo.id}/follow-up", json={})
        assert response.status_code == 403
        assert response.status_code != 422
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, owner.id)
        session.commit()
        session.close()


def test_anonymous_private_follow_up_malformed_body_stays_404(hosted_client) -> None:
    session, store, owner, demo, private = _demo_and_private(hosted_client)
    try:
        response = hosted_client.post(f"/api/v1/research-runs/{private.id}/follow-up", json={})
        assert response.status_code == 404
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, owner.id)
        session.commit()
        session.close()


def test_anonymous_demo_source_preference_malformed_body_is_forbidden(hosted_client) -> None:
    session, store, owner, demo, private = _demo_and_private(hosted_client)
    try:
        response = hosted_client.post(
            f"/api/v1/research-runs/{demo.id}/source-preferences",
            json={},
        )
        assert response.status_code == 403
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, owner.id)
        session.commit()
        session.close()


def test_anonymous_demo_hitl_respond_malformed_body_is_forbidden(hosted_client) -> None:
    session, store, owner, demo, _private = _demo_and_private(hosted_client)
    review_id = uuid4()
    try:
        response = hosted_client.post(
            f"/api/v1/research-runs/{demo.id}/reviews/{review_id}/respond",
            json={},
        )
        assert response.status_code == 403
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, owner.id)
        session.commit()
        session.close()
