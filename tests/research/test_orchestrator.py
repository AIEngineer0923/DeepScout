from unittest.mock import patch

import pytest
from deepscout_core.domain.enums import ResearchRunStatus
from deepscout_core.domain.schemas import (
    PlannerOutput,
    PlannerQuestion,
    ResearchRunCreate,
    SearchResult,
)
from deepscout_research.orchestrator import ResearchOrchestrator


class FakeSearchProvider:
    provider_name = "fake"

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        timeout_s: float = 15.0,
    ) -> list[SearchResult]:
        return [
            SearchResult(
                url=f"https://example.com/{query[:8].replace(' ', '-').lower()}",
                title="Example",
                snippet="Result snippet",
            )
        ]


@pytest.mark.postgres
def test_orchestrator_persists_plan_sources_and_terminates(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="EV battery chemistries", budget=settings.default_research_budget()),
        settings,
    )
    fake_plan = PlannerOutput(
        approach="Compare chemistries",
        success_criteria="Identify leading chemistry",
        questions=[PlannerQuestion(text="Which chemistry leads energy density?", priority=1)],
    )
    with patch("deepscout_research.orchestrator.build_research_plan", return_value=fake_plan):
        orchestrator = ResearchOrchestrator(store, settings, FakeSearchProvider())
        result = orchestrator.execute(run.id)

    assert result.final_status in {
        ResearchRunStatus.COMPLETED,
        ResearchRunStatus.BUDGET_EXHAUSTED,
    }
    questions = store.list_questions(run.id)
    assert len(questions) == 1
    assert questions[0].status.value in {"answered", "insufficient_evidence"}
