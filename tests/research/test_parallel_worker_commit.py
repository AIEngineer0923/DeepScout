import re
from unittest.mock import MagicMock, patch

import pytest
from deepscout_core.domain.enums import ResearchTaskStatus
from deepscout_core.domain.schemas import (
    PlannerOutput,
    PlannerQuestion,
    PlannerTask,
    ResearchPlanWrite,
    ResearchRunCreate,
    SearchResult,
)
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.planner import planner_output_to_write
from deepscout_research.workers.pool import ResearchWorkerPool
from sqlalchemy import text


class FakeSearchProvider:
    provider_name = "fake"

    def search(self, query: str, **_kwargs):
        from deepscout_core.domain.schemas import SearchResult

        lowered = query.casefold()
        domain = (
            "example.net"
            if "independent" in lowered
            else "example.org"
            if "official" in lowered
            else "iana.org"
        )
        slug = re.sub(r"[^a-z0-9]+", "-", lowered)[:48].strip("-")
        return [
            SearchResult(
                url=f"https://{domain}/{slug}",
                title="Example",
                snippet=f"Two independent chemistry questions. {query}",
            )
        ]


class SequenceSearchProvider:
    provider_name = "sequence"

    def __init__(self, results: list[list[SearchResult]]) -> None:
        self.results = list(results)
        self.calls = 0

    def search(self, query: str, **_kwargs) -> list[SearchResult]:
        self.calls += 1
        if not self.results:
            return []
        return self.results.pop(0)


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
def test_ready_worker_batch_drains_without_database_deadlock(postgres_ready, settings) -> None:
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
                    "snippet": f"Two independent chemistry questions about {suffix.upper()}",
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


@pytest.mark.postgres
def test_zero_admissible_yield_reformulates_then_blocks_task(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Coastal wetland restoration outcomes"), settings)
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="research",
            success_criteria="source-backed result",
            questions=["Coastal wetland restoration outcomes"],
            tasks=[PlannerTask(task_key="wetland", objective="Measure restoration outcomes")],
        ),
    )
    task = store.list_tasks(run.id)[0]
    store.update_task_status(task.id, ResearchTaskStatus.READY)
    irrelevant = [
        SearchResult(
            url="https://example.com/arbitration",
            title="Commercial arbitration",
            snippet="Rules for international commercial disputes",
        )
    ]
    provider = SequenceSearchProvider([irrelevant, irrelevant])
    first_state = {
        "status": "completed",
        "query": "wetland outcomes",
        "search_results": [item.model_dump() for item in irrelevant],
    }
    with patch("deepscout_research.workers.pool.run_worker_graph", return_value=first_state):
        result = ResearchWorkerPool(
            MagicMock(), settings, provider, inline_store=store
        ).execute_batch(run.id, store.list_tasks(run.id), iteration=1)[0]

    persisted = store.list_tasks(run.id)[0]
    assert result.success is False
    assert result.error == "no_admissible_sources_after_retries"
    assert persisted.status == ResearchTaskStatus.BLOCKED
    assert persisted.retry_count == 2
    assert len(store.list_tool_executions(run.id)) == 3
    assert store.list_sources(run.id) == []


@pytest.mark.postgres
def test_relevant_first_hit_still_runs_bounded_corroboration_search(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Coastal wetland restoration outcomes"), settings)
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="research",
            success_criteria="source-backed result",
            questions=["Coastal wetland restoration outcomes"],
            tasks=[PlannerTask(task_key="wetland", objective="Measure restoration outcomes")],
        ),
    )
    task = store.list_tasks(run.id)[0]
    store.update_task_status(task.id, ResearchTaskStatus.READY)
    irrelevant = SearchResult(
        url="https://example.com/arbitration",
        title="Commercial arbitration",
        snippet="Rules for international commercial disputes",
    )
    relevant = SearchResult(
        url="https://example.org/wetland-study",
        title="Coastal wetland restoration outcomes",
        snippet="Measured coastal wetland restoration outcomes over five years",
    )
    corroborating = SearchResult(
        url="https://example.net/wetland-restoration",
        title="Independent coastal wetland restoration study",
        snippet="Independent five-year measurements of coastal wetland restoration outcomes",
    )
    third = SearchResult(
        url="https://iana.org/wetland-restoration",
        title="Additional coastal wetland restoration evidence",
        snippet="Separate measurements of coastal wetland restoration outcomes over five years",
    )
    provider = SequenceSearchProvider([[relevant], [corroborating], [third]])
    first_state = {
        "status": "completed",
        "query": "wetland outcomes",
        "search_results": [irrelevant.model_dump()],
    }
    with patch("deepscout_research.workers.pool.run_worker_graph", return_value=first_state):
        result = ResearchWorkerPool(
            MagicMock(), settings, provider, inline_store=store
        ).execute_batch(run.id, store.list_tasks(run.id), iteration=1)[0]

    persisted = store.list_tasks(run.id)[0]
    assert result.success is True, {
        "result": result,
        "sources": [item.canonical_url for item in store.list_sources(run.id)],
        "candidates": [(item.query, item.url) for item in store.list_search_candidates(run.id)],
    }
    assert result.sources_added == 3
    assert persisted.status == ResearchTaskStatus.COMPLETED
    assert persisted.retry_count == 3
    assert len(store.list_tool_executions(run.id)) == 4
    assert len(store.list_sources(run.id)) == 3
