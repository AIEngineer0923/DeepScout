import pytest
from deepscout_core.domain.enums import ResearchTaskStatus
from deepscout_core.domain.schemas import PlannerTask, ResearchPlanWrite, ResearchRunCreate
from deepscout_core.settings import get_settings


@pytest.fixture
def settings():
    return get_settings()


@pytest.mark.postgres
def test_completed_task_is_not_regressed(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Idempotent complete", budget=settings.default_research_budget()),
        settings,
    )
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="s",
            success_criteria="c",
            questions=["Q1"],
            tasks=[PlannerTask(task_key="q1", objective="Q1", priority=1)],
        ),
    )
    task = store.list_tasks(run.id)[0]
    store.update_task_status(task.id, ResearchTaskStatus.COMPLETED)
    store.update_task_status(task.id, ResearchTaskStatus.RUNNING)
    store.commit()
    assert store.list_tasks(run.id)[0].status == ResearchTaskStatus.COMPLETED


@pytest.mark.postgres
def test_reclaim_stale_running_task(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Reclaim stale", budget=settings.default_research_budget()),
        settings,
    )
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="s",
            success_criteria="c",
            questions=["Q1"],
            tasks=[PlannerTask(task_key="q1", objective="Q1", priority=1)],
        ),
    )
    task = store.list_tasks(run.id)[0]
    store.update_task_status(task.id, ResearchTaskStatus.RUNNING)
    reclaimed = store.reclaim_stale_running_tasks(run.id, stale_after_seconds=0)
    store.commit()
    assert reclaimed == 1
    assert store.list_tasks(run.id)[0].status == ResearchTaskStatus.READY


@pytest.mark.postgres
def test_duplicate_ready_claim_is_atomic(store, settings, db_session) -> None:
    from uuid import uuid4

    run = store.create_run(
        ResearchRunCreate(goal="Atomic claim", budget=settings.default_research_budget()),
        settings,
    )
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="s",
            success_criteria="c",
            questions=["Q1"],
            tasks=[PlannerTask(task_key="q1", objective="Q1", priority=1)],
        ),
    )
    task = store.list_tasks(run.id)[0]
    store.update_task_status(task.id, ResearchTaskStatus.READY)
    owner_a = uuid4()
    owner_b = uuid4()
    first = store.claim_ready_task(task.id, owner_a)
    second = store.claim_ready_task(task.id, owner_b)
    store.commit()
    asserted = store.list_tasks(run.id)[0]
    assert first is True
    assert second is False
    assert asserted.worker_id == owner_a
    assert asserted.status == ResearchTaskStatus.RUNNING


@pytest.mark.postgres
def test_stale_worker_cannot_complete_after_reassignment(store, settings, db_session) -> None:
    from uuid import uuid4

    run = store.create_run(
        ResearchRunCreate(goal="Stale writer", budget=settings.default_research_budget()),
        settings,
    )
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="s",
            success_criteria="c",
            questions=["Q1"],
            tasks=[PlannerTask(task_key="q1", objective="Q1", priority=1)],
        ),
    )
    task = store.list_tasks(run.id)[0]
    owner_a = uuid4()
    owner_b = uuid4()
    store.update_task_status(task.id, ResearchTaskStatus.READY)
    assert store.claim_ready_task(task.id, owner_a) is True
    store.reclaim_stale_running_tasks(run.id, stale_after_seconds=0)
    store.update_task_status(task.id, ResearchTaskStatus.READY)
    assert store.claim_ready_task(task.id, owner_b) is True
    store.update_task_status(task.id, ResearchTaskStatus.COMPLETED, worker_id=owner_a)
    store.commit()
    current = store.list_tasks(run.id)[0]
    assert current.worker_id == owner_b
    assert current.status == ResearchTaskStatus.RUNNING
