import pytest
from deepscout_core.domain.enums import AgentRole, CostReportStatus, ResearchPhase
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.domain.usage import TokenUsageRecord
from deepscout_core.settings import get_settings
from deepscout_core.types import ProviderKind
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS


@pytest.mark.postgres
def test_application_cost_persisted_when_catalog_maps(store, db_session) -> None:
    settings = get_settings()
    run = store.create_run(ResearchRunCreate(goal="Cost persistence"), settings)
    usage = TokenUsageRecord(
        research_run_id=run.id,
        phase=ResearchPhase.PLAN,
        agent_role=AgentRole.PLANNER,
        provider=ProviderKind.GOOGLE.value,
        model=DEFAULT_CHAT_MODELS[ProviderKind.GOOGLE],
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
    )
    from deepscout_research.usage.pricing import DEFAULT_PRICING_CATALOG

    cost, status = DEFAULT_PRICING_CATALOG.estimate_cost(usage)
    store.record_token_usage(
        usage, pricing_version=DEFAULT_PRICING_CATALOG.version, cost_usd=cost, cost_status=status
    )
    summary = store.get_usage_summary(run.id)
    assert status == CostReportStatus.ESTIMATED
    assert summary.cost_usd is not None and summary.cost_usd > 0
    assert summary.cost_status == CostReportStatus.ESTIMATED
    assert summary.evaluation_cost_usd is None


@pytest.mark.postgres
def test_evaluator_usage_excluded_from_application_cost(store, db_session) -> None:
    settings = get_settings()
    run = store.create_run(ResearchRunCreate(goal="Eval cost isolation"), settings)
    from deepscout_research.usage.pricing import DEFAULT_PRICING_CATALOG

    application = TokenUsageRecord(
        research_run_id=run.id,
        phase=ResearchPhase.PLAN,
        agent_role=AgentRole.PLANNER,
        provider=ProviderKind.GOOGLE.value,
        model=DEFAULT_CHAT_MODELS[ProviderKind.GOOGLE],
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
    )
    evaluation = TokenUsageRecord(
        research_run_id=run.id,
        phase=ResearchPhase.REPORT,
        agent_role=AgentRole.EVALUATOR,
        provider=ProviderKind.GOOGLE.value,
        model=DEFAULT_CHAT_MODELS[ProviderKind.GOOGLE],
        input_tokens=8000,
        output_tokens=400,
        total_tokens=8400,
    )
    app_cost, app_status = DEFAULT_PRICING_CATALOG.estimate_cost(application)
    eval_cost, eval_status = DEFAULT_PRICING_CATALOG.estimate_cost(evaluation)
    store.record_token_usage(
        application, pricing_version="2026-08-21", cost_usd=app_cost, cost_status=app_status
    )
    store.record_token_usage(
        evaluation, pricing_version="2026-08-21", cost_usd=eval_cost, cost_status=eval_status
    )
    summary = store.get_usage_summary(run.id)
    assert summary.total_tokens == 150
    assert summary.cost_usd == app_cost
    assert summary.evaluation_total_tokens == 8400
    assert summary.evaluation_cost_usd == eval_cost
