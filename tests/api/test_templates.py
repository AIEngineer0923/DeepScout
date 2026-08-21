from uuid import uuid4

import pytest
from deepscout_core.domain.schemas import ResearchRunCreate, ResearchTemplateCreate


@pytest.mark.postgres
def test_template_crud_roundtrip(store, settings) -> None:
    created = store.create_template(
        ResearchTemplateCreate(name="Preset", goal="Compare two chemistries", research_mode="quick")
    )
    listed = store.list_templates()
    assert listed[0].id == created.id
    assert listed[0].goal.startswith("Compare")
    assert store.delete_template(created.id) is True
    assert store.list_templates() == []


@pytest.mark.postgres
def test_list_run_card_metrics_is_batched(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="metrics"), settings)
    metrics = store.list_run_card_metrics([run.id, uuid4()])
    assert metrics[run.id]["source_count"] == 0
    assert metrics[run.id]["task_count"] == 0
