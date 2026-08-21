import pytest
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import get_settings
from deepscout_evaluation.run_evals import evaluate_research_run


@pytest.fixture
def settings():
    return get_settings()


@pytest.mark.postgres
def test_evaluate_research_run_on_empty_artifacts(store, settings, db_session) -> None:
    run = store.create_run(
        ResearchRunCreate(goal="Eval empty", budget=settings.default_research_budget()),
        settings,
    )
    store.commit()
    result = evaluate_research_run(store, run.id)
    assert result["termination_correct"] is False
    assert result["unsupported_claim_rate"] == 0.0
    assert result["dag_cycle_free"] is True
    assert result["task_count"] == 0
    assert result["status"] == "pending"
