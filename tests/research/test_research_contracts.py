"""Tests for research contracts, source authority, coverage, and final report."""

from __future__ import annotations

import pytest
from deepscout_core.domain.contracts import (
    RequirementCoverageStatus,
    SourceConstraintMode,
)
from deepscout_core.domain.enums import ClaimVerificationStatus
from deepscout_core.domain.schemas import (
    ClaimWrite,
    EvidenceWrite,
    PlannerOutput,
    PlannerQuestion,
    ResearchPlanWrite,
    ResearchRunCreate,
    SearchCandidateWrite,
    SearchResult,
    SourceSnapshotWrite,
    SourceWrite,
)
from deepscout_research.contracts.coverage import evaluate_coverage, gap_search_queries
from deepscout_research.contracts.evidence_relevance import (
    claim_specificity_allowed,
    is_evidence_relevant,
)
from deepscout_research.contracts.extract import build_research_contract, derive_report_contract
from deepscout_research.contracts.source_authority import (
    classify_source_authority,
    is_source_admissible,
    violates_only_constraint,
)
from deepscout_research.phases.final_critic import run_final_answer_critic
from deepscout_research.phases.report import generate_report


def _planner(goal: str) -> PlannerOutput:
    return PlannerOutput(
        approach="Structured research plan",
        success_criteria="Answer all material parts of the user request with authoritative evidence.",
        questions=[PlannerQuestion(text=goal, priority=1)],
    )


def test_build_research_contract_detects_italian_official_only() -> None:
    goal = (
        "Identifica il Presidente della Commissione europea. "
        "Utilizza esclusivamente fonti istituzionali ufficiali dell'UE."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    assert contract.source_constraints
    assert contract.source_constraints[0].mode == SourceConstraintMode.ONLY
    assert "ec.europa.eu" in contract.source_constraints[0].values


def test_build_research_contract_detects_official_only_eu() -> None:
    goal = (
        "Explain GPAI obligations under the EU AI Act. "
        "Use only official EU institutional sources."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    assert contract.source_constraints
    assert contract.source_constraints[0].mode == SourceConstraintMode.ONLY
    assert "europa.eu" in contract.source_constraints[0].values


def test_derive_report_contract_regulatory() -> None:
    goal = "Explain EU AI Act GPAI obligations and enforcement timeline."
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    report = derive_report_contract(contract)
    assert report.report_type.value == "regulatory_analysis"
    assert report.include_chronology is True


def test_source_admission_blocks_non_official_under_only_policy() -> None:
    goal = "Use only official EU institutional sources to identify GPAI guidance."
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    assert violates_only_constraint("https://www.morrisons.com/finance", contract=contract)
    admissible, reason = is_source_admissible(
        "https://www.morrisons.com/finance",
        contract=contract,
    )
    assert not admissible
    assert reason == "violates_only_source_constraint"
    admissible_eu, _ = is_source_admissible(
        "https://digital-strategy.ec.europa.eu/en/policies/gpai",
        contract=contract,
    )
    assert admissible_eu


def test_classify_source_authority_peer_reviewed() -> None:
    meta = classify_source_authority(url="https://doi.org/10.1000/example")
    assert meta.peer_reviewed is True


def test_evidence_relevance_rejects_noise() -> None:
    goal = "EU AI Act GPAI obligations"
    assert not is_evidence_relevant(
        quote="Morrisons supermarket debt restructuring announcement",
        query="GPAI obligations",
        goal=goal,
    )


def test_claim_specificity_requires_numeric_support() -> None:
    assert not claim_specificity_allowed(
        claim="Break-even occurs at 70,000 km",
        evidence_quote="BEVs generally have lower lifecycle emissions.",
    )
    assert claim_specificity_allowed(
        claim="Break-even occurs at 70,000 km",
        evidence_quote="The break-even distance is approximately 70,000 km in EU scenarios.",
    )


@pytest.mark.postgres
def test_report_generation_omits_planner_task_leak(store, settings) -> None:
    goal = "Compare BEV and ICE lifecycle GHG emissions in Europe."
    run = store.create_run(
        ResearchRunCreate(goal=goal, budget=settings.default_research_budget()),
        settings,
    )
    planner = _planner(goal)
    contract = build_research_contract(goal=goal, planner=planner, output_language="en")
    report_contract = derive_report_contract(contract)
    store.merge_config_snapshot(
        run.id,
        {
            "research_contract": contract.model_dump(mode="json"),
            "report_contract": report_contract.model_dump(mode="json"),
        },
    )
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="s",
            success_criteria=contract.requirements[-1].text,
            questions=contract.user_facing_questions,
        ),
    )
    generate_report(store, settings, run.id)
    report = store.get_report(run.id)
    assert report is not None
    body = report.body_markdown
    assert "## Questions" not in body
    assert "Collect" not in body
    assert "## Sources Cited" in body
    assert "## Evidence" not in body


@pytest.mark.postgres
def test_coverage_and_final_critic_partial_answer(store, settings) -> None:
    goal = "Compare BEV and ICE lifecycle GHG in Europe with quantitative estimates."
    run = store.create_run(
        ResearchRunCreate(goal=goal, budget=settings.default_research_budget()),
        settings,
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    store.merge_config_snapshot(run.id, {"research_contract": contract.model_dump(mode="json")})
    store.save_plan(
        run.id,
        ResearchPlanWrite(strategy="s", success_criteria="quant", questions=[goal]),
    )
    source, _ = store.add_source(
        run.id,
        SourceWrite(
            canonical_url="https://theicct.org/publication/eu-ev-lifecycle",
            title="ICCT EU lifecycle",
            domain="theicct.org",
        ),
    )
    question = store.list_questions(run.id)[0]
    store.add_search_candidates(
        run.id,
        SearchCandidateWrite(
            query="BEV ICE lifecycle GHG Europe quantitative",
            provider="fake",
            results=[
                SearchResult(
                    url=source.canonical_url,
                    title="ICCT",
                    snippet="lifecycle GHG comparison Europe BEV ICE quantitative estimate",
                )
            ],
            question_id=question.id,
        ),
    )
    snapshot_text = (
        "In studied EU scenarios, battery electric vehicles show lower lifecycle greenhouse gas "
        "emissions than comparable internal combustion vehicles. One study reports a break-even "
        "distance of approximately 70,000 km under average grid assumptions."
    )
    snapshot = store.add_snapshot(
        source.id,
        SourceSnapshotWrite(content=snapshot_text, mime_type="text/plain"),
    )
    claim = store.add_claim(
        run.id,
        ClaimWrite(
            statement=(
                "In studied EU scenarios, battery electric vehicles show lower lifecycle greenhouse "
                "gas emissions than comparable internal combustion vehicles."
            ),
            source_id=source.id,
            question_id=question.id,
        ),
    )
    store.attach_evidence(
        claim.id,
        EvidenceWrite(snapshot_id=snapshot.id, quote=snapshot_text[:400]),
    )
    store.update_claim_verification(claim.id, ClaimVerificationStatus.VERIFIED)
    coverage = evaluate_coverage(store, run.id, contract)
    assert any(entry.status == RequirementCoverageStatus.SUPPORTED for entry in coverage.entries)
    generate_report(store, settings, run.id)
    critic = run_final_answer_critic(store, run.id)
    assert critic.verdict.value in {
        "pass",
        "revision_required",
        "research_gap",
        "blocked_by_evidence",
    }
    gaps = gap_search_queries(contract, coverage)
    assert isinstance(gaps, list)
