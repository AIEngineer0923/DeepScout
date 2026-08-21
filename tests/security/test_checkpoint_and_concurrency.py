import uuid

import pytest
from deepscout_core.domain.enums import ResearchTaskStatus
from deepscout_core.domain.schemas import PlannerTask, ResearchPlanWrite, ResearchRunCreate
from deepscout_core.settings import get_settings
from deepscout_research.workers.langgraph_worker import worker_thread_id


@pytest.mark.postgres
def test_duplicate_ready_task_claim_rejected(store, db_session) -> None:

    settings = get_settings()
    run = store.create_run(ResearchRunCreate(goal="Claim race"), settings)
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="s",
            success_criteria="c",
            questions=["Q"],
            tasks=[PlannerTask(task_key="q1", objective="Q", priority=1, allowed_tools=["web_search"])],
        ),
    )
    task = store.list_tasks(run.id)[0]
    store.update_task_status(task.id, ResearchTaskStatus.READY)
    first = uuid.uuid4()
    second = uuid.uuid4()
    assert store.claim_ready_task(task.id, first) is True
    assert store.claim_ready_task(task.id, second) is False


def test_worker_thread_id_is_run_and_task_scoped() -> None:
    run_id = uuid.uuid4()
    task_a = uuid.uuid4()
    task_b = uuid.uuid4()
    assert worker_thread_id(run_id=run_id, task_id=task_a) != worker_thread_id(run_id=run_id, task_id=task_b)
    assert str(run_id) in worker_thread_id(run_id=run_id, task_id=task_a)
