"""Offline deterministic final-report quality gate (no live web)."""

from __future__ import annotations

import pytest
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
from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.extract import build_research_contract, derive_report_contract
from deepscout_research.contracts.requirement_attribution import attribute_requirements
from deepscout_research.contracts.temporal_evidence import (
    evidence_supports_applicable_now,
    evidence_supports_future_or_transitional,
)
from deepscout_research.phases.final_critic import run_final_answer_critic
from deepscout_research.phases.report import generate_report


def _planner(goal: str) -> PlannerOutput:
    return PlannerOutput(
        approach="Structured research plan",
        success_criteria=(
            "Answer all material parts of the user request with authoritative evidence."
        ),
        questions=[PlannerQuestion(text=goal, priority=1)],
    )


def test_temporal_evidence_distinguishes_applicability() -> None:
    now_quote = (
        "Chapter V obligations entered into application on 2 August 2025 for GPAI providers."
    )
    later_quote = "Transitional provisions apply until 2 August 2027 for systemic-risk models."
    assert evidence_supports_applicable_now(statement="", quote=now_quote)
    assert evidence_supports_future_or_transitional(statement="", quote=later_quote)


def test_lfp_nmc_requirement_attribution() -> None:
    goal = (
        "Confronta LFP e NMC su ciclo di vita, densità energetica, sicurezza termica, "
        "driver di costo ed effetti dell'ingegneria di pacco."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    quote = (
        "LFP thermal runaway onset occurs around 270-300C whereas high-nickel NMC initiates "
        "around 150-210C; NMC offers higher energy density while LFP improves cycle life."
    )
    req_ids = attribute_requirements(statement=quote, quote=quote, contract=contract)
    assert "R_compare" in req_ids


@pytest.mark.postgres
def test_offline_lfp_nmc_coverage_passes(store, settings) -> None:
    goal = (
        "Confronta LFP e NMC ad alto contenuto di nichel su ciclo di vita, densità energetica, "
        "sicurezza termica, driver di costo ed effetti dell'ingegneria di pacco."
    )
    run = store.create_run(
        ResearchRunCreate(goal=goal, budget=settings.default_research_budget()),
        settings,
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal), output_language="en")
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
        ResearchPlanWrite(strategy="s", success_criteria="compare", questions=[goal]),
    )
    source, _ = store.add_source(
        run.id,
        SourceWrite(
            canonical_url="https://www.nrel.gov/news/program/2024/battery-chemistries.html",
            title="NREL battery chemistries",
            domain="nrel.gov",
        ),
    )
    question = store.list_questions(run.id)[0]
    snippet = "LFP NMC cycle life energy density thermal safety pack engineering comparison"
    store.add_search_candidates(
        run.id,
        SearchCandidateWrite(
            query="LFP NMC comparison cycle life energy density thermal safety",
            provider="fixture",
            results=[SearchResult(url=source.canonical_url, title="NREL", snippet=snippet)],
            question_id=question.id,
        ),
    )
    snapshot_text = (
        "LFP cells show thermal runaway onset around 270-300C while high-nickel NMC initiates "
        "around 150-210C. NMC offers higher gravimetric energy density; LFP improves cycle life "
        "and thermal stability. Pack engineering reduces the effective energy-density gap."
    )
    snapshot = store.add_snapshot(
        source.id,
        SourceSnapshotWrite(content=snapshot_text, mime_type="text/plain"),
    )
    quote = snapshot_text
    req_ids = attribute_requirements(statement=quote, quote=quote, contract=contract)
    claim = store.add_claim(
        run.id,
        ClaimWrite(statement=quote, source_id=source.id, question_id=question.id),
    )
    store.attach_evidence(
        claim.id,
        EvidenceWrite(
            snapshot_id=snapshot.id,
            quote=quote,
            extraction_metadata={"requirement_ids": req_ids},
        ),
    )
    store.update_claim_verification(claim.id, ClaimVerificationStatus.VERIFIED)
    coverage = evaluate_coverage(store, run.id, contract)
    compare = next(entry for entry in coverage.entries if entry.requirement_id == "R_compare")
    assert compare.status.value == "supported"
    generate_report(store, settings, run.id)
    critic = run_final_answer_critic(store, run.id)
    assert critic.verdict.value == "pass"


@pytest.mark.postgres
def test_offline_eu_gpai_regulatory_temporal_coverage(store, settings) -> None:
    goal = (
        "Spiega gli obblighi GPAI del Regolamento UE sull'IA nel 2026, distinguendo gli obblighi "
        "già applicabili da quelli successivi."
    )
    run = store.create_run(
        ResearchRunCreate(
            goal=goal, budget=settings.default_research_budget(), output_language="it"
        ),
        settings,
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal), output_language="it")
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
        ResearchPlanWrite(strategy="s", success_criteria="timeline", questions=[goal]),
    )
    source, _ = store.add_source(
        run.id,
        SourceWrite(
            canonical_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689",
            title="EU AI Act",
            domain="eur-lex.europa.eu",
        ),
    )
    question = store.list_questions(run.id)[0]
    store.add_search_candidates(
        run.id,
        SearchCandidateWrite(
            query="EU AI Act GPAI obligations applicable dates transitional",
            provider="fixture",
            results=[
                SearchResult(
                    url=source.canonical_url,
                    title="AI Act",
                    snippet="GPAI obligations entered into application on 2 August 2025",
                )
            ],
            question_id=question.id,
        ),
    )
    now_text = "GPAI transparency obligations entered into application on 2 August 2025."
    later_text = (
        "Systemic-risk GPAI models must comply with additional obligations by 2 August 2027."
    )
    snapshot = store.add_snapshot(
        source.id,
        SourceSnapshotWrite(content=f"{now_text} {later_text}", mime_type="text/plain"),
    )
    for statement in (now_text, later_text):
        req_ids = attribute_requirements(statement=statement, quote=statement, contract=contract)
        claim = store.add_claim(
            run.id,
            ClaimWrite(statement=statement, source_id=source.id, question_id=question.id),
        )
        store.attach_evidence(
            claim.id,
            EvidenceWrite(
                snapshot_id=snapshot.id,
                quote=statement,
                extraction_metadata={"requirement_ids": req_ids},
            ),
        )
        store.update_claim_verification(claim.id, ClaimVerificationStatus.VERIFIED)
    coverage = evaluate_coverage(store, run.id, contract)
    apply = next(entry for entry in coverage.entries if entry.requirement_id == "R_reg_apply")
    assert apply.status.value in {"supported", "partial"}
