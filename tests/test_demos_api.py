"""Public demo catalog API."""

from __future__ import annotations

from uuid import uuid4

import pytest
from deepscout_core.domain.enums import ResearchRunStatus
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.presentation import (
    load_bundled_presentation,
    merge_presentation_into_public_demo,
)
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


def _completed_demo(store: ResearchStore, settings: Settings, slug: str):
    run = store.create_run(
        ResearchRunCreate(goal=f"Demo goal for {slug}", research_mode="quick"),
        settings,
        owner_principal_id=None,
    )
    row = store.get_run_row(run.id)
    row.status = ResearchRunStatus.COMPLETED
    bundled = load_bundled_presentation(slug)
    if bundled:
        public_demo = merge_presentation_into_public_demo({"slug": slug}, slug)
        store.merge_config_snapshot(run.id, {"public_demo": public_demo})
    row.is_public_demo = True
    row.public_slug = slug
    store.commit()
    return run.id


def test_demos_catalog_lists_only_published_completed(hosted_client, postgres_ready):
    settings = Settings()
    session = get_session_factory(database_url())()
    store = ResearchStore(session)
    demo_id = _completed_demo(store, settings, f"demo-{uuid4().hex[:8]}")
    private = store.create_run(
        ResearchRunCreate(goal="private run", research_mode="quick"),
        settings,
        owner_principal_id=None,
    )
    store.commit()
    session.close()

    response = hosted_client.get("/api/v1/demos")
    assert response.status_code == 200
    payload = response.json()
    ids = {item["id"] for item in payload["items"]}
    assert str(demo_id) in ids
    assert str(private.id) not in ids
    assert payload["items"][0]["public_slug"]


def test_demo_slug_lookup(hosted_client, postgres_ready):
    settings = Settings()
    session = get_session_factory(database_url())()
    store = ResearchStore(session)
    slug = f"lookup-{uuid4().hex[:6]}"
    demo_id = _completed_demo(store, settings, slug)
    store.commit()
    session.close()

    ok = hosted_client.get(f"/api/v1/demos/{slug}")
    assert ok.status_code == 200
    assert ok.json()["id"] == str(demo_id)
    missing = hosted_client.get("/api/v1/demos/does-not-exist")
    assert missing.status_code == 404
