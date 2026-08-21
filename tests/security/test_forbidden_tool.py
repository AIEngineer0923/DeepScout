from unittest.mock import MagicMock

import pytest
from deepscout_core.domain.enums import ResearchTaskStatus
from deepscout_core.domain.schemas import PlannerTask, ResearchPlanWrite, ResearchRunCreate
from deepscout_core.settings import get_settings
from deepscout_research.workers.pool import ResearchWorkerPool


class _NoopSearch:
    provider_name = "noop"

    def search(self, query: str, *, max_results: int = 5, timeout_s: float = 15.0):
        raise AssertionError("search must not run when the tool is forbidden")


@pytest.mark.postgres
def test_worker_cannot_call_forbidden_tool(store, db_session) -> None:
    settings = get_settings()
    run = store.create_run(ResearchRunCreate(goal="Forbidden tool"), settings)
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="s",
            success_criteria="c",
            questions=["Q"],
            tasks=[PlannerTask(task_key="q1", objective="Q", priority=1, allowed_tools=["none"])],
        ),
    )
    task = store.list_tasks(run.id)[0]
    store.update_task_status(task.id, ResearchTaskStatus.READY)
    ready = store.list_tasks(run.id)[0]
    pool = ResearchWorkerPool(MagicMock(), settings, _NoopSearch(), inline_store=store)
    results = pool.execute_batch(run.id, [ready], iteration=1)
    assert results[0].success is False
    assert results[0].error == "tool_not_allowed"
    assert store.list_tasks(run.id)[0].status == ResearchTaskStatus.FAILED
