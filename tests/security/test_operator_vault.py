"""Operator maintainer vault sync — only the configured GitHub account."""

from __future__ import annotations

from uuid import uuid4

import pytest
from deepscout_core.settings import Settings
from deepscout_persistence.identity import (
    create_session,
    list_credentials,
    upsert_oauth_principal,
)
from deepscout_research.credentials.operator_vault import (
    is_operator_github_account,
    sync_operator_vault_from_env,
    try_sync_operator_vault,
)
from fastapi.testclient import TestClient
from tests.db_helpers import database_url

pytestmark = pytest.mark.postgres

OPERATOR_GITHUB_ID = "255975034"


@pytest.fixture
def hosted_client(monkeypatch, postgres_ready):
    monkeypatch.setenv("DEEPSCOUT_DEPLOYMENT_MODE", "hosted")
    monkeypatch.setenv("SESSION_SECRET", "session-secret-for-tests-not-used-directly")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "0" * 32)
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "test-github-id")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "test-github-secret")
    monkeypatch.setenv("MAINTAINER_VAULT_GITHUB_ID", OPERATOR_GITHUB_ID)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-maintainer-key-12345678")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-maintainer-key-12345678")
    monkeypatch.setenv("LANGSMITH_API_KEY", "langsmith-maintainer-key-12345678")
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "1000")
    monkeypatch.setenv("RATE_LIMIT_MUTATING_MAX", "1000")
    from deepscout_api.app import app

    return TestClient(app)


def _session():
    from deepscout_persistence.session import get_session_factory

    return get_session_factory(database_url())()


def _github_user(session, *, account_id: str, name: str):
    principal = upsert_oauth_principal(
        session,
        provider="github",
        provider_account_id=account_id,
        display_name=name,
        email=None,
        email_verified=False,
        avatar_url=None,
    )
    token = create_session(session, principal.id)
    session.commit()
    return principal, token


def test_operator_github_match() -> None:
    settings = Settings(
        _env_file=None,
        DEEPSCOUT_DEPLOYMENT_MODE="hosted",
        MAINTAINER_VAULT_GITHUB_ID=OPERATOR_GITHUB_ID,
    )
    assert is_operator_github_account(
        settings,
        provider="github",
        provider_account_id=OPERATOR_GITHUB_ID,
    )
    assert not is_operator_github_account(
        settings,
        provider="github",
        provider_account_id="999999",
    )
    assert not is_operator_github_account(
        settings,
        provider="google",
        provider_account_id=OPERATOR_GITHUB_ID,
    )


def test_operator_vault_sync_only_for_configured_github_user(hosted_client) -> None:
    session = _session()
    settings = Settings(_env_file=None)
    operator, operator_token = _github_user(
        session, account_id=OPERATOR_GITHUB_ID, name="Operator"
    )
    other, other_token = _github_user(session, account_id=f"other-{uuid4().hex[:8]}", name="Other")
    try:
        synced_operator = sync_operator_vault_from_env(session, operator.id, settings)
        synced_other = sync_operator_vault_from_env(session, other.id, settings)
        session.commit()
        assert "google" in synced_operator
        assert "tavily" in synced_operator
        assert "langsmith" in synced_operator
        assert synced_other == []
        operator_rows = {row.provider for row in list_credentials(session, operator.id)}
        assert {"google", "tavily", "langsmith"}.issubset(operator_rows)
        assert list_credentials(session, other.id) == []

        profile = hosted_client.get("/api/v1/account", cookies={"ds_session": operator_token})
        assert profile.status_code == 200
        payload = profile.json()
        assert payload["operator_vault_synced"] is True
        configured = {
            row["provider"] for row in payload["credentials"] if row["configured"]
        }
        assert {"google", "tavily", "langsmith"}.issubset(configured)

        other_profile = hosted_client.get("/api/v1/account", cookies={"ds_session": other_token})
        assert other_profile.json()["operator_vault_synced"] is False
        assert all(not row["configured"] for row in other_profile.json()["credentials"])

        operator_settings = hosted_client.get(
            "/api/v1/settings", cookies={"ds_session": operator_token}
        )
        assert operator_settings.status_code == 200
        assert operator_settings.json()["langsmith"]["connected"] is True
        assert operator_settings.json()["langsmith"]["tracing"] is True
        assert operator_settings.json()["providers"]["langsmith"]["configured"] is True

        other_settings = hosted_client.get("/api/v1/settings", cookies={"ds_session": other_token})
        assert other_settings.json()["langsmith"]["connected"] is False
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, operator.id)
        delete_principal_data(session, other.id)
        session.commit()
        session.close()


def test_try_sync_operator_vault_is_noop_without_match(hosted_client) -> None:
    session = _session()
    settings = Settings(_env_file=None)
    other, _ = _github_user(session, account_id=f"other-{uuid4().hex[:8]}", name="Other")
    try:
        assert try_sync_operator_vault(session, other.id, settings) == []
    finally:
        from deepscout_persistence.identity import delete_principal_data

        delete_principal_data(session, other.id)
        session.commit()
        session.close()
