import pytest
from deepscout_core.domain.enums import ResearchRunStatus, ResearchTaskStatus
from deepscout_core.domain.schemas import PlannerTask, ResearchPlanWrite, ResearchRunCreate
from deepscout_core.settings import get_settings
from deepscout_research.phases.text_utils import locate_quote_in_content


@pytest.fixture
def settings():
    return get_settings()


@pytest.mark.postgres
def test_cancel_run_marks_active_tasks_cancelled(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Cancel propagation", budget=settings.default_research_budget()),
        settings,
    )
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="s",
            success_criteria="c",
            questions=["Q1"],
            tasks=[
                PlannerTask(
                    task_key="q1",
                    objective="Q1",
                    priority=1,
                    allowed_tools=["web_search"],
                )
            ],
        ),
    )
    task = store.list_tasks(run.id)[0]
    store.update_task_status(task.id, ResearchTaskStatus.RUNNING)
    store.cancel_run(run.id)
    store.commit()
    updated_task = store.list_tasks(run.id)[0]
    updated_run = store.get_run(run.id)
    assert updated_run is not None
    assert updated_run.status == ResearchRunStatus.CANCELLED
    assert updated_task.status == ResearchTaskStatus.CANCELLED


def test_locate_quote_rejects_injection_markup() -> None:
    content = "NMC batteries use nickel manganese cobalt cathodes for energy density."
    assert locate_quote_in_content("nickel manganese cobalt cathodes", content) is not None
    assert locate_quote_in_content("<script>alert(1)</script>", content) is None
    assert locate_quote_in_content("javascript:alert(1)", content) is None
