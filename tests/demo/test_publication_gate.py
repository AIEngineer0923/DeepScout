"""Publication fail-closed integration tests."""

from __future__ import annotations

import pytest
from deepscout_core.domain.enums import ResearchRunStatus
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_persistence.models import ResearchRunRow
from deepscout_research.demo.publication import publish_demo
from sqlalchemy import select
from tests.db_helpers import database_url

pytestmark = pytest.mark.postgres


def _completed_run(store: ResearchStore, settings: Settings):
    run = store.create_run(
        ResearchRunCreate(goal="Publication gate test", research_mode="quick"),
        settings,
        owner_principal_id=None,
    )
    row = store.get_run_row(run.id)
    row.status = ResearchRunStatus.COMPLETED
    store.commit()
    return run


def test_publish_without_bundles_fails_closed(postgres_ready):
    settings = Settings()
    session = get_session_factory(database_url())()
    store = ResearchStore(session)
    run = _completed_run(store, settings)
    with pytest.raises(ValueError, match="PRESENTATION_EN_MISSING"):
        publish_demo(store, run.id, "not-a-real-demo-slug", require_completed=False)
    session.close()


def test_publish_catalog_slug_without_tasks_fails(postgres_ready):
    settings = Settings()
    session = get_session_factory(database_url())()
    store = ResearchStore(session)
    slug = "multi-hop-research"
    existing = store._session.scalar(
        select(ResearchRunRow).where(ResearchRunRow.public_slug == slug)
    )
    if existing is not None:
        existing.is_public_demo = False
        existing.public_slug = None
        store._session.flush()
    run = _completed_run(store, settings)
    with pytest.raises(ValueError, match="PRESENTATION_SCHEMA_INVALID|run has no tasks"):
        publish_demo(store, run.id, slug, require_completed=False)
    session.close()
