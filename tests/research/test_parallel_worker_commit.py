from unittest.mock import patch

import pytest
from deepscout_core.domain.schemas import (
    PlannerOutput,
    PlannerQuestion,
    ResearchRunCreate,
)
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.planner import planner_output_to_write
from deepscout_research.workers.pool import ResearchWorkerPool


class FakeSearchProvider:
    provider_name = "fake"

    def search(self, query: str, *, max_results: int = 5, timeout_s: float = 15.0):
        from deepscout_core.domain.schemas import SearchResult

        return [
            SearchResult(
                url=f"https://example.com/{query[:8].replace(' ', '-').lower()}",
                title="Example",
                snippet="Result snippet",
            )
        ]


@pytest.mark.postgres
def test_orchestrator_commits_before_parallel_workers(store, settings) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="EV battery chemistries", budget=settings.default_research_budget()),
        settings,
    )
    fake_plan = PlannerOutput(
        approach="Compare chemistries",
        success_criteria="Identify leading chemistry",
        questions=[PlannerQuestion(text="Which chemistry leads energy density?", priority=1)],
    )
    store.save_plan(run.id, planner_output_to_write(fake_plan))
    commits: list[str] = []
    original_commit = store.commit

    def tracked_commit() -> None:
        commits.append("commit")
        original_commit()

    store.commit = tracked_commit  # type: ignore[method-assign]
    with patch.object(ResearchWorkerPool, "execute_batch", return_value=[]):
        orchestrator = ResearchOrchestrator(
            store,
            settings.model_copy(update={"research_workers_inline": False}),
            FakeSearchProvider(),
        )
        orchestrator.execute_research_batch(run.id, iteration=1)

    assert commits.count("commit") >= 2
