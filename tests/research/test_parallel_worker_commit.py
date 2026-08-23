from unittest.mock import patch

import pytest
from deepscout_core.domain.schemas import (
    PlannerOutput,
    PlannerQuestion,
    ResearchRunCreate,
)
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.planner import planner_output_to_write
from deepscout_research.workers.pool import ResearchWorkerPool
from sqlalchemy import text


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

    assert commits.count("commit") >= 3


@pytest.mark.postgres
def test_ready_worker_batch_drains_without_database_deadlock(
    postgres_ready, settings
) -> None:
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    run = store.create_run(
        ResearchRunCreate(
            goal="Two independent chemistry questions",
            budget=settings.default_research_budget(),
        ),
        settings,
    )
    fake_plan = PlannerOutput(
        approach="Parallel",
        success_criteria="Both questions researched",
        questions=[
            PlannerQuestion(text="What is LFP?", priority=1),
            PlannerQuestion(text="What is NMC?", priority=1),
            PlannerQuestion(text="What is LCO?", priority=1),
            PlannerQuestion(text="What is LMO?", priority=1),
        ],
    )
    store.save_plan(run.id, planner_output_to_write(fake_plan))
    store.commit()

    def graph_state(**kwargs):
        suffix = kwargs["objective"].split()[2].strip("?").casefold()
        return {
            "status": "ok",
            "query": f"battery {suffix}",
            "search_results": [
                {
                    "url": f"https://example.com/{suffix}",
                    "title": suffix.upper(),
                    "snippet": f"{suffix.upper()} chemistry",
                },
            ],
        }

    worker_results = []
    execute_batch = ResearchWorkerPool.execute_batch

    def capture_batch(pool, *args, **kwargs):
        results = execute_batch(pool, *args, **kwargs)
        worker_results.extend(results)
        return results

    try:
        with (
            patch("deepscout_research.workers.pool.run_worker_graph", side_effect=graph_state),
            patch.object(ResearchWorkerPool, "execute_batch", new=capture_batch),
        ):
            orchestrator = ResearchOrchestrator(
                store,
                settings.model_copy(
                    update={
                        "research_workers_inline": False,
                        "agent_max_total_workers": 4,
                    }
                ),
                FakeSearchProvider(),
            )
            result = orchestrator.execute_research_batch(run.id, iteration=1)
        assert result is not None
        assert len(worker_results) == 4
        assert all(item.success for item in worker_results), "\n---\n".join(
            item.error or "success" for item in worker_results
        )
        statuses = {task.status.value for task in store.list_tasks(run.id)}
        assert statuses == {"completed"}
    finally:
        session.rollback()
        session.execute(text("DELETE FROM research_runs WHERE id = :run_id"), {"run_id": run.id})
        session.commit()
        session.close()
