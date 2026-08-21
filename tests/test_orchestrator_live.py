"""Live orchestrator test — requires local .env secrets."""

from __future__ import annotations

import pytest
from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings, get_settings
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.search.tavily import TavilyWebSearchProvider


def _live_settings() -> Settings | None:
    settings = get_settings()
    if not settings.google_api_key:
        return None
    try:
        settings.require_tavily_api_key()
    except ValueError:
        return None
    return settings


@pytest.mark.integration
@pytest.mark.postgres
def test_live_orchestrator_low_budget_run(store) -> None:
    live = _live_settings()
    if live is None:
        pytest.skip("GOOGLE_API_KEY and TAVILY_API_KEY required for live orchestrator test")

    run = store.create_run(
        ResearchRunCreate(
            goal="What are two common EV battery chemistries?",
            budget=ResearchBudget(
                max_iterations=1,
                max_tool_calls=1,
                max_sources=2,
                max_total_tokens=5_000,
            ),
        ),
        live,
    )
    with TavilyWebSearchProvider(live) as search:
        orchestrator = ResearchOrchestrator(store, live, search)
        result = orchestrator.execute(run.id)

    assert result.iterations >= 1
    assert store.list_questions(run.id)
