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


@pytest.mark.postgres
def test_duplicate_execute_reuses_active_job(store, db_session) -> None:
    from deepscout_research.jobs.service import JobService

    settings = get_settings()
    run = store.create_run(ResearchRunCreate(goal="Execute once"), settings)
    jobs = JobService(store)
    first = jobs.enqueue_execute_run(run.id)
    second = jobs.enqueue_execute_run(run.id)
    assert first.id == second.id


@pytest.mark.postgres
def test_resume_reuses_active_job_then_cancel_wins(store, db_session) -> None:
    from deepscout_research.jobs.service import JobService

    settings = get_settings()
    run = store.create_run(ResearchRunCreate(goal="Resume once"), settings)
    jobs = JobService(store)
    first = jobs.enqueue_resume_run(run.id)
    second = jobs.enqueue_resume_run(run.id)
    assert first.id == second.id
    store.cancel_run(run.id)
    assert store.get_run(run.id).status.value == "cancelled"


@pytest.mark.postgres
def test_source_dedupe_returns_existing_row(store, db_session) -> None:
    from deepscout_core.domain.schemas import SourceWrite

    settings = get_settings()
    run = store.create_run(ResearchRunCreate(goal="Source dedupe"), settings)
    first, created_first = store.add_source(
        run.id, SourceWrite(canonical_url="https://example.com/a")
    )
    second, created_second = store.add_source(
        run.id, SourceWrite(canonical_url="https://example.com/a")
    )
    assert created_first is True
    assert created_second is False
    assert first.id == second.id
