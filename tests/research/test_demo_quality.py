"""Tests for public demo quality gate."""

from __future__ import annotations

import pytest
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.quality import review_demo_candidate
from tests.db_helpers import database_url

pytestmark = pytest.mark.postgres


def test_quality_fails_sparse_sources(postgres_ready):
    settings = Settings()
    session = get_session_factory(database_url())()
    store = ResearchStore(session)
    run = store.create_run(
        ResearchRunCreate(goal="test", research_mode="quick"),
        settings,
        owner_principal_id=None,
    )
    row = store.get_run_row(run.id)
    from deepscout_core.domain.enums import ResearchRunStatus

    row.status = ResearchRunStatus.COMPLETED
    store.commit()
    review = review_demo_candidate(store, run.id, slug="eu-ai-act-gpai-2026")
    session.close()
    assert review["PUBLICATION_DECISION"] == "FAIL"
    assert any("SOURCE" in code for code in review["reason_codes"])
