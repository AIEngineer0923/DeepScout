import pytest
from deepscout_core.domain.budget import BudgetExhaustedError, ResearchBudget
from deepscout_core.domain.enums import ResearchTaskStatus
from deepscout_core.domain.schemas import PlannerTask, ResearchPlanWrite, ResearchRunCreate
from deepscout_core.settings import get_settings
from deepscout_research.budget_gate import BudgetGate
from deepscout_research.workers.langgraph_worker import worker_thread_id


@pytest.mark.postgres
def test_budget_reservation_race_second_call_exhausts(store, db_session) -> None:
    settings = get_settings()
    run = store.create_run(
        ResearchRunCreate(
            goal="Budget race",
            budget=ResearchBudget(
                max_iterations=1,
                max_wall_time_seconds=30,
                max_total_tokens=1000,
                max_cost_usd=1,
                max_sources=1,
                max_tool_calls=1,
            ),
            research_mode="quick",
        ),
        settings,
    )
    gate = BudgetGate(store)
    gate.reserve_tool_call(run.id, note="first")
    with pytest.raises(BudgetExhaustedError):
        gate.reserve_tool_call(run.id, note="second")


@pytest.mark.postgres
def test_create_run_persists_mode_and_output_language(store, db_session) -> None:
    settings = get_settings()
    run = store.create_run(
        ResearchRunCreate(goal="Mode persistence", research_mode="deep", output_language="it"),
        settings,
    )
    assert run.research_mode == "deep"
    assert run.output_language == "it"
    assert run.budget.max_sources >= 60


@pytest.mark.postgres
def test_cancel_vs_running_task(store, db_session) -> None:
    settings = get_settings()
    run = store.create_run(ResearchRunCreate(goal="Cancel vs fan-in"), settings)
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="s",
            success_criteria="c",
            questions=["Q"],
            tasks=[
                PlannerTask(task_key="q1", objective="Q", priority=1, allowed_tools=["web_search"]),
            ],
        ),
    )
    task = store.list_tasks(run.id)[0]
    store.update_task_status(task.id, ResearchTaskStatus.RUNNING)
    store.cancel_run(run.id)
    assert store.get_run(run.id).status.value == "cancelled"
    assert store.list_tasks(run.id)[0].status == ResearchTaskStatus.CANCELLED


def test_mismatched_checkpoint_thread_ids_are_isolated() -> None:
    run_a = "11111111-1111-1111-1111-111111111111"
    run_b = "22222222-2222-2222-2222-222222222222"
    task = "33333333-3333-3333-3333-333333333333"
    from uuid import UUID

    assert worker_thread_id(run_id=UUID(run_a), task_id=UUID(task)) != worker_thread_id(
        run_id=UUID(run_b), task_id=UUID(task)
    )
