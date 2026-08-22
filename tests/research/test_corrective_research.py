"""Tests for corrective research, contradiction quality, and report revision."""

from __future__ import annotations

import pytest
from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.contracts import RequirementCoverageStatus
from deepscout_core.domain.schemas import PlannerOutput, PlannerQuestion, ResearchRunCreate
from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.extract import build_research_contract
from deepscout_research.phases.contradiction import _classify_pair
from deepscout_research.runtime.corrective_research import evaluate_corrective_research


def test_tradeoff_not_classified_as_contradiction() -> None:
    assert _classify_pair(
        "NMC cathodes offer higher energy density in EV packs.",
        "LFP cathodes offer higher thermal stability and cycle life.",
    ) is None


def test_true_contradiction_detected() -> None:
    reason = _classify_pair(
        "BEV lifecycle emissions are lower than ICE in studied EU scenarios.",
        "BEV lifecycle emissions are higher than ICE in studied EU scenarios.",
    )
    assert reason is not None
    assert "Opposing" in reason or "Semantic" in reason


@pytest.mark.postgres
def test_corrective_research_schedules_gap_task(store, settings) -> None:
    goal = (
        "Compare BEV and ICE lifecycle GHG in Europe. "
        "Quantify break-even mileage where published."
    )
    run = store.create_run(
        ResearchRunCreate(goal=goal, budget=settings.default_research_budget()),
        settings,
    )
    contract = build_research_contract(
        goal=goal,
        planner=PlannerOutput(
            approach="plan",
            success_criteria="quantitative comparison",
            questions=[PlannerQuestion(text=goal, priority=1)],
        ),
    )
    store.merge_config_snapshot(run.id, {"research_contract": contract.model_dump(mode="json")})
    coverage = evaluate_coverage(store, run.id, contract)
    assert any(
        entry.status
        in {
            RequirementCoverageStatus.NOT_RESEARCHED,
            RequirementCoverageStatus.SEARCHED,
            RequirementCoverageStatus.SEARCHED_NO_EVIDENCE,
        }
        for entry in coverage.entries
    )
    decision = evaluate_corrective_research(
        store,
        run.id,
        settings=settings,
        budget=ResearchBudget(max_iterations=3, max_tool_calls=5, max_sources=10),
        consumption=store.get_consumption(run.id),
    )
    assert decision.apply is True
    assert decision.new_tasks
    assert decision.new_tasks[0].objective
