import pytest
from deepscout_core.domain.enums import ResearchRunStatus
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import get_settings
from deepscout_evaluation.matrix import build_evaluation_rows
from deepscout_evaluation.persist import load_evaluation_rows


@pytest.fixture
def settings():
    return get_settings()


@pytest.mark.postgres
def test_persist_and_reload_evaluation_results(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Eval persist", budget=settings.default_research_budget()),
        settings,
    )
    store.commit()
    rows = build_evaluation_rows({"budget_compliance": True, "dag_cycle_free": True})
    store.replace_evaluation_results(run.id, rows)
    store.commit()
    loaded = store.list_evaluation_results(run.id)
    assert len(loaded) == len(rows)
    budget = next(item for item in loaded if item["evaluator_id"] == "budget_compliance")
    assert budget["status"] == "passed"
    assert budget["value"] is True


@pytest.mark.postgres
def test_load_evaluation_rows_backfills_terminal_runs(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Eval backfill", budget=settings.default_research_budget()),
        settings,
    )
    store.update_run_status(run.id, ResearchRunStatus.COMPLETED)
    store.commit()
    rows = load_evaluation_rows(store, run.id, include_evals=True, backfill=True)
    assert rows
    assert store.list_evaluation_results(run.id)
