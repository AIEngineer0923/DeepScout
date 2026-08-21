"""Fork creates a new run and does not copy pending HITL reviews."""

from __future__ import annotations

import pytest
from deepscout_core.domain.enums import ReviewReasonCode
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_research.hitl import HumanReviewService
from deepscout_research.runtime.config_snapshot import build_config_snapshot


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        LLM_PROVIDER=ProviderKind.GOOGLE,
        HITL_ENABLED=True,
        HITL_BUDGET_EXTENSION_REQUIRES_REVIEW=True,
    )


@pytest.mark.postgres
def test_fork_does_not_copy_reviews(store, settings) -> None:
    parent = store.create_run(
        ResearchRunCreate(goal="fork parent", budget=settings.default_research_budget()),
        settings,
        config_snapshot=build_config_snapshot(settings),
    )
    service = HumanReviewService(store, settings)
    review_id = service.create_budget_extension_review(parent.id)
    child = store.create_run(
        ResearchRunCreate(goal=parent.goal, budget=settings.default_research_budget()),
        settings,
        config_snapshot=build_config_snapshot(settings),
        parent_run_id=parent.id,
        fork_reason="before_synthesis",
    )
    assert child.id != parent.id
    row = store.get_run_row(child.id)
    assert row is not None
    assert row.parent_run_id == parent.id
    assert store.get_pending_review(child.id, ReviewReasonCode.BUDGET_EXTENSION) is None
    assert store.get_review_request(review_id).research_run_id == parent.id
    assert row.config_snapshot["provider_transport_max_retries"] == 0
