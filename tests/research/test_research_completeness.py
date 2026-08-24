"""Domain-neutral regression tests for material research completeness."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.contracts import (
    AnswerRequirement,
    CoverageGapCause,
    CoverageMap,
    CoverageMapEntry,
    EvidenceType,
    RequirementCoverageStatus,
    RequirementKind,
    ResearchContract,
    SourceClass,
)
from deepscout_core.domain.enums import (
    ClaimVerificationStatus,
    ResearchRunStatus,
    ToolExecutionStatus,
)
from deepscout_core.domain.research_profiles import budget_for_research_mode, research_profile
from deepscout_core.domain.schemas import (
    ClaimWrite,
    EvidenceWrite,
    PlannerOutput,
    PlannerQuestion,
    PlannerTask,
    ResearchPlanWrite,
    ResearchRunCreate,
    SearchCandidateWrite,
    SearchResult,
    SourceSnapshotWrite,
    SourceWrite,
    ToolExecutionWrite,
)
from deepscout_evaluation.persist import persist_research_evaluations
from deepscout_persistence.models import LearningExperimentJobRow
from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.extract import build_research_contract, derive_report_contract
from deepscout_research.contracts.numeric_constraints import (
    extract_numeric_constraints,
    markdown_allocation_errors,
)
from deepscout_research.contracts.query_planning import (
    contract_research_tasks,
    search_query_variants,
)
from deepscout_research.contracts.requirement_attribution import requirements_for_query
from deepscout_research.phases.final_critic import run_final_answer_critic
from deepscout_research.phases.report import _append_sources_cited
from deepscout_research.phases.structured_extract import enrich_structured_evidence
from deepscout_research.runtime.corrective_research import material_gap_requirement_ids
from sqlalchemy import select


def _contract(*requirements: AnswerRequirement) -> ResearchContract:
    return ResearchContract(
        primary_question="Assess the system across all requested dimensions.",
        requirements=list(requirements),
    )


def _run(store, settings, contract: ResearchContract, *, budget: ResearchBudget | None = None):
    run = store.create_run(
        ResearchRunCreate(
            goal=contract.primary_question,
            budget=budget or settings.default_research_budget(),
        ),
        settings,
    )
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
            strategy="bounded requirement research",
            success_criteria="material coverage",
            questions=[contract.primary_question],
        ),
    )
    return run


def _add_evidence(
    store,
    run_id,
    *,
    requirement_id: str,
    query: str,
    statement: str,
    url: str,
    source_class: SourceClass,
    evidence_type: EvidenceType = EvidenceType.UNKNOWN,
):
    source, _ = store.add_source(
        run_id,
        SourceWrite(canonical_url=url, title="Regression source", domain=url.split("/")[2]),
    )
    question = store.list_questions(run_id)[0]
    store.add_search_candidates(
        run_id,
        SearchCandidateWrite(
            query=query,
            provider="fixture",
            results=[SearchResult(url=url, title="Regression source", snippet=statement)],
            question_id=question.id,
        ),
    )
    snapshot = store.add_snapshot(
        source.id,
        SourceSnapshotWrite(content=statement, mime_type="text/plain"),
    )
    claim = store.add_claim(
        run_id,
        ClaimWrite(statement=statement, source_id=source.id, question_id=question.id),
    )
    store.attach_evidence(
        claim.id,
        EvidenceWrite(
            snapshot_id=snapshot.id,
            quote=statement,
            extraction_metadata={
                "requirement_ids": [requirement_id],
                "source_class": source_class.value,
                "evidence_type": evidence_type.value,
            },
        ),
    )
    store.update_claim_verification(claim.id, ClaimVerificationStatus.VERIFIED)


def test_contract_preserves_material_bullets() -> None:
    goal = """Assess a hypothetical intervention:
- Quantify measured outcome rates and uncertainty.
- Compare Option Alpha vs Option Beta on the same dimensions.
- Distinguish observations, experiments, and model simulations.
- Explain study methodology and limitations.
- Use peer-reviewed primary studies where available.
"""
    planner = PlannerOutput(
        approach="decompose user requirements",
        success_criteria="answer every material bullet",
        questions=[PlannerQuestion(text=goal, priority=1)],
    )
    contract = build_research_contract(goal=goal, planner=planner)
    material = [item for item in contract.requirements if item.materiality == "central"]
    assert len(material) == 5
    assert {item.kind for item in material} >= {
        RequirementKind.QUANTIFICATION,
        RequirementKind.COMPARISON,
        RequirementKind.DISTINCTION,
        RequirementKind.METHODOLOGY,
        RequirementKind.SOURCE_POLICY,
    }


@pytest.mark.postgres
def test_formally_complete_report_cannot_hide_uncovered_material_requirement(
    store,
    settings,
) -> None:
    contract = _contract(
        AnswerRequirement(requirement_id="R_fact", text="Measure the primary outcome"),
        AnswerRequirement(requirement_id="R_method", text="Explain the study methodology"),
    )
    run = _run(store, settings, contract)
    _add_evidence(
        store,
        run.id,
        requirement_id="R_fact",
        query="measure primary outcome authoritative evidence",
        statement="The primary outcome was observed in the study cohort.",
        url="https://www.nrel.gov/research/outcome",
        source_class=SourceClass.RESEARCH_BODY,
    )
    store.save_report_draft(
        run.id,
        title="Complete-looking report",
        body_markdown=(
            "# Report\n\n## Executive Summary\nA polished summary.\n\n"
            "## Analysis\nThe observed outcome is discussed.\n\n"
            "## Limitations and Uncertainty\nGeneral limitations.\n\n"
            "## Sources Cited\n1. [Source](https://www.nrel.gov/research/outcome)\n"
        ),
    )
    coverage = evaluate_coverage(store, run.id, contract)
    fact = next(item for item in coverage.entries if item.requirement_id == "R_fact")
    method = next(item for item in coverage.entries if item.requirement_id == "R_method")
    assert fact.status == RequirementCoverageStatus.SUPPORTED
    assert method.status == RequirementCoverageStatus.NOT_RESEARCHED
    assert run_final_answer_critic(store, run.id).verdict.value == "research_gap"


@pytest.mark.postgres
def test_quantitative_requirement_needs_attributable_number(store, settings) -> None:
    contract = _contract(
        AnswerRequirement(
            requirement_id="R_quant",
            text="Quantify the measured outcome rate",
            kind=RequirementKind.QUANTIFICATION,
            quantification_required=True,
        )
    )
    run = _run(store, settings, contract)
    _add_evidence(
        store,
        run.id,
        requirement_id="R_quant",
        query="quantify measured outcome rate dataset",
        statement="The measured outcome rate was materially higher in the observed group.",
        url="https://www.nrel.gov/research/rate",
        source_class=SourceClass.RESEARCH_BODY,
    )
    entry = evaluate_coverage(store, run.id, contract).entries[0]
    assert entry.status == RequirementCoverageStatus.PARTIAL
    assert entry.gap_cause == CoverageGapCause.NUMERIC_EVIDENCE_MISSING


@pytest.mark.postgres
def test_timeline_requirement_needs_every_requested_timeframe(store, settings) -> None:
    contract = _contract(
        AnswerRequirement(
            requirement_id="R_timeline",
            text="Measure recovery after 1, 10, and 20 years",
            kind=RequirementKind.TIMELINE,
        )
    )
    run = _run(store, settings, contract)
    _add_evidence(
        store,
        run.id,
        requirement_id="R_timeline",
        query="recovery after 1 10 20 years longitudinal monitoring",
        statement="The disturbed habitat remained visibly altered after 44 years.",
        url="https://www.nrel.gov/research/recovery",
        source_class=SourceClass.RESEARCH_BODY,
    )
    entry = evaluate_coverage(store, run.id, contract).entries[0]
    assert entry.status == RequirementCoverageStatus.PARTIAL
    assert entry.gap_cause == CoverageGapCause.TIMELINE_INCOMPLETE


@pytest.mark.postgres
def test_requested_comparison_needs_both_named_subjects(store, settings) -> None:
    contract = _contract(
        AnswerRequirement(
            requirement_id="R_compare",
            text="Compare Option Alpha vs Option Beta on reliability",
            kind=RequirementKind.COMPARISON,
            comparison_subjects=["Option Alpha", "Option Beta"],
        )
    )
    run = _run(store, settings, contract)
    _add_evidence(
        store,
        run.id,
        requirement_id="R_compare",
        query="Option Alpha Option Beta comparative reliability study",
        statement="Option Alpha had high reliability in the study.",
        url="https://www.nrel.gov/research/alpha",
        source_class=SourceClass.RESEARCH_BODY,
    )
    entry = evaluate_coverage(store, run.id, contract).entries[0]
    assert entry.status == RequirementCoverageStatus.PARTIAL
    assert entry.gap_cause == CoverageGapCause.COMPARISON_INCOMPLETE


@pytest.mark.postgres
def test_secondary_discovery_does_not_satisfy_primary_scientific_portfolio(store, settings) -> None:
    contract = _contract(
        AnswerRequirement(
            requirement_id="R_science",
            text="Report observed effects from primary empirical studies",
            expected_source_classes=[SourceClass.PEER_REVIEWED, SourceClass.RESEARCH_BODY],
            required_evidence_types=[EvidenceType.PRIMARY_EMPIRICAL],
        )
    )
    run = _run(store, settings, contract)
    _add_evidence(
        store,
        run.id,
        requirement_id="R_science",
        query="observed effects primary empirical studies",
        statement="A news report described effects attributed to an unnamed study.",
        url="https://www.reuters.com/world/example",
        source_class=SourceClass.NEWS_MEDIA,
        evidence_type=EvidenceType.SECONDARY_REPORTING,
    )
    entry = evaluate_coverage(store, run.id, contract).entries[0]
    assert entry.status == RequirementCoverageStatus.PARTIAL
    assert entry.gap_cause == CoverageGapCause.SOURCE_PORTFOLIO_INADEQUATE


@pytest.mark.postgres
def test_zero_result_search_and_budget_exhaustion_have_distinct_causes(store, settings) -> None:
    requirement = AnswerRequirement(
        requirement_id="R_missing",
        text="Find measured evidence for the proposed effect",
    )
    normal = _run(store, settings, _contract(requirement))
    store.save_tool_execution(
        normal.id,
        ToolExecutionWrite(
            tool_name="web_search",
            input_summary="find measured evidence proposed effect",
            output_summary="0 results",
            status=ToolExecutionStatus.SUCCESS,
        ),
    )
    normal_entry = evaluate_coverage(store, normal.id, _contract(requirement)).entries[0]
    assert normal_entry.gap_cause == CoverageGapCause.SEARCH_NO_RESULTS

    exhausted = _run(
        store,
        settings,
        _contract(requirement),
        budget=ResearchBudget(max_iterations=0),
    )
    exhausted_entry = evaluate_coverage(store, exhausted.id, _contract(requirement)).entries[0]
    assert exhausted_entry.gap_cause == CoverageGapCause.BUDGET_EXHAUSTED


def test_bibliography_is_canonicalized_and_localized() -> None:
    source = SimpleNamespace(
        title="Evidence",
        domain="example.org",
        canonical_url="https://example.org/evidence",
    )
    body = (
        "# Report\n\n## Analysis\nText.\n\n# Sources Cited\n"
        "1. [Old](https://example.org/evidence)\n\n## Fonti citate\n"
        "1. [Old](https://example.org/evidence)\n"
    )
    rendered = _append_sources_cited(body, [source], "it")
    assert rendered.count("Fonti citate") == 1
    assert "Sources Cited" not in rendered


def test_mode_profiles_increase_depth_with_hard_caps() -> None:
    quick = research_profile("quick")
    standard = research_profile("standard")
    deep = research_profile("deep")
    assert quick.max_requirement_tasks < standard.max_requirement_tasks < deep.max_requirement_tasks
    assert (
        quick.search_results_per_query
        < standard.search_results_per_query
        < deep.search_results_per_query
    )
    assert quick.max_coverage_rounds < standard.max_coverage_rounds < deep.max_coverage_rounds
    assert (
        quick.max_coverage_rounds * quick.gap_queries_per_round
        < standard.max_coverage_rounds * standard.gap_queries_per_round
        < deep.max_coverage_rounds * deep.gap_queries_per_round
    )
    base = ResearchBudget()
    quick_budget = budget_for_research_mode(base, "quick")
    standard_budget = budget_for_research_mode(base, "standard")
    deep_budget = budget_for_research_mode(base, "deep")
    assert quick_budget.max_iterations == 2
    assert standard_budget == base
    assert deep_budget.max_iterations == 8
    assert quick_budget.max_tool_calls < standard_budget.max_tool_calls < deep_budget.max_tool_calls


def test_contract_tasks_target_missing_requirements_with_mode_bound() -> None:
    contract = _contract(
        *[
            AnswerRequirement(
                requirement_id=f"R{index}",
                text=f"Quantify outcome dimension {index} from measured data",
                kind=RequirementKind.QUANTIFICATION,
                quantification_required=True,
            )
            for index in range(1, 15)
        ]
    )
    quick = contract_research_tasks(contract, research_mode="quick")
    standard = contract_research_tasks(contract, research_mode="standard")
    deep = contract_research_tasks(contract, research_mode="deep")
    assert len(quick) == research_profile("quick").max_requirement_tasks
    assert len(standard) == research_profile("standard").max_requirement_tasks
    assert len(deep) == research_profile("deep").max_requirement_tasks
    assert all("quantitative measurements" in task.objective for task in standard)
    assert all(task.dependency_reason.startswith("contract_requirement:") for task in deep)


def test_requirement_queries_retain_primary_subject_context() -> None:
    contract = ResearchContract(
        primary_question="Assess the coastal intervention, including engineering and ecology.",
        requirements=[
            AnswerRequirement(
                requirement_id="R_engineering",
                text="Quantify construction methods and measured reliability",
                kind=RequirementKind.QUANTIFICATION,
                quantification_required=True,
            )
        ],
    )
    task = contract_research_tasks(contract, research_mode="standard")[0]
    assert "coastal intervention" in task.objective
    assert "construction methods" in task.objective


def test_long_conversational_goal_keeps_named_subject_in_reformulation() -> None:
    contract = ResearchContract(
        primary_question=(
            "Devo preparare oggi un fantacalcio Serie A a 8 partecipanti con modificatore. "
            "Confronta titolarità, rigori, infortuni e calendario prima dell'asta."
        )
    )
    variants = search_query_variants(
        "probabilità reale di titolarità e disponibilità",
        contract,
        max_variants=3,
    )
    assert variants
    assert all("fantacalcio" in query.casefold() for query in variants)
    assert all("titolarità" in query.casefold() for query in variants)


def test_valid_semantic_plan_is_not_expanded_one_task_per_bullet() -> None:
    contract = _contract(
        AnswerRequirement(requirement_id="R1", text="Quantify reliability"),
        AnswerRequirement(requirement_id="R2", text="Compare total cost"),
    )
    existing = [
        PlannerTask(
            task_key="system_tradeoffs",
            objective="Compare reliability and total cost of the named systems",
        )
    ]
    assert contract_research_tasks(contract, existing_tasks=existing) == []


def test_conflicting_budget_constraints_and_table_arithmetic_are_deterministic() -> None:
    constraints, conflicts = extract_numeric_constraints(
        "Use a total budget of 1000 credits. The total budget must be 500 credits."
    )
    assert {item.value for item in constraints} == {"500", "1000"}
    assert conflicts == ["budget_total: 1000, 500 credits"]
    assert markdown_allocation_errors(
        "| Item | Budget |\n|---|---:|\n| A | 60 |\n| B | 30 |\n| Total | 100 |"
    ) == ["allocation_sum_mismatch:90!=100"]


def test_requirement_query_provenance_survives_cross_language_evidence() -> None:
    contract = ResearchContract(
        primary_question="Valuta il recupero dell'ecosistema costiero.",
        requirements=[
            AnswerRequirement(
                requirement_id="R_recovery",
                text="recupero a 1, 10 e 20 anni",
                kind=RequirementKind.TIMELINE,
            )
        ],
    )
    matched = requirements_for_query(
        query="ecosistema costiero recupero 1 10 20 anni longitudinal follow-up",
        contract=contract,
    )
    assert matched == ["R_recovery"]


@pytest.mark.postgres
def test_incremental_extraction_merges_requirement_provenance(store, settings) -> None:
    contract = _contract(
        AnswerRequirement(requirement_id="R_one", text="First measured outcome"),
        AnswerRequirement(requirement_id="R_two", text="Second measured outcome"),
    )
    run = _run(store, settings, contract)
    source, _ = store.add_source(
        run.id,
        SourceWrite(canonical_url="https://example.org/result", title="Result"),
    )
    snapshot = store.add_snapshot(
        source.id,
        SourceSnapshotWrite(content="The measured outcome was 44 percent.", mime_type="text/plain"),
    )
    claim = store.add_claim(
        run.id,
        ClaimWrite(statement="The measured outcome was 44 percent.", source_id=source.id),
    )
    evidence = store.attach_evidence(
        claim.id,
        EvidenceWrite(
            snapshot_id=snapshot.id,
            quote=claim.statement,
            extraction_metadata={"requirement_ids": ["R_one"]},
        ),
    )
    store.merge_evidence_metadata(
        claim.id,
        snapshot.id,
        claim.statement,
        {"requirement_ids": ["R_two"]},
    )
    assert evidence.extraction_metadata["requirement_ids"] == ["R_one", "R_two"]


def test_corrective_priority_favors_unattempted_central_gaps() -> None:
    contract = _contract(
        AnswerRequirement(requirement_id="R_first", text="First central requirement"),
        AnswerRequirement(requirement_id="R_second", text="Second central requirement"),
        AnswerRequirement(
            requirement_id="R_secondary",
            text="Secondary context",
            materiality="secondary",
        ),
    )
    coverage = CoverageMap(
        entries=[
            CoverageMapEntry(
                requirement_id="R_first",
                status=RequirementCoverageStatus.PARTIAL,
                corrective_attempts=2,
            ),
            CoverageMapEntry(
                requirement_id="R_second",
                status=RequirementCoverageStatus.NOT_RESEARCHED,
            ),
            CoverageMapEntry(
                requirement_id="R_secondary",
                status=RequirementCoverageStatus.NOT_RESEARCHED,
            ),
        ]
    )
    assert material_gap_requirement_ids(coverage, contract) == ["R_second", "R_first"]


@pytest.mark.postgres
def test_generic_contract_does_not_run_regulatory_structured_extract(store, settings) -> None:
    contract = _contract(
        AnswerRequirement(requirement_id="R_effect", text="Measure ecological recovery")
    )
    run = _run(store, settings, contract)
    source, _ = store.add_source(
        run.id,
        SourceWrite(
            canonical_url="https://example.org/ecology",
            title="Ecology study",
            domain="example.org",
        ),
    )
    store.add_snapshot(
        source.id,
        SourceSnapshotWrite(
            content=(
                "The monitoring protocol applies from 2026. "
                "Measured ecological recovery remained incomplete after ten years."
            ),
            mime_type="text/plain",
        ),
    )
    stats = enrich_structured_evidence(store, run.id)
    assert stats["temporal_claims"] == 0
    assert stats["verified_entities"] == 0
    assert store.list_claims(run.id) == []


@pytest.mark.postgres
def test_terminal_completeness_failure_creates_case_candidate_and_experiment(
    store,
    settings,
) -> None:
    active_before = store.get_active_learning_policy(
        policy_key="global.corrective_research",
        owner_principal_id=None,
    )
    contract = _contract(
        AnswerRequirement(requirement_id="R_covered", text="Measure the observed outcome"),
        AnswerRequirement(requirement_id="R_missing", text="Explain the sampling methodology"),
    )
    run = _run(store, settings, contract)
    _add_evidence(
        store,
        run.id,
        requirement_id="R_covered",
        query="measure observed outcome research report",
        statement="The observed outcome was documented for the study population.",
        url="https://www.nrel.gov/research/observed",
        source_class=SourceClass.RESEARCH_BODY,
    )
    store.save_report_draft(
        run.id,
        title="Partial research",
        body_markdown=(
            "# Partial research\n\n## Executive Summary\nPartial findings.\n\n"
            "## Analysis\nThe observed outcome was documented.\n\n"
            "## Limitations and Uncertainty\nSampling methodology remains unresolved.\n\n"
            "## Sources Cited\n1. [Source](https://www.nrel.gov/research/observed)\n"
        ),
    )
    critic = run_final_answer_critic(store, run.id)
    store.merge_config_snapshot(run.id, {"final_critic": critic.model_dump(mode="json")})
    store.update_run_status(run.id, ResearchRunStatus.RUNNING)
    store.update_run_status(run.id, ResearchRunStatus.COMPLETED)

    rows = persist_research_evaluations(store, run.id)
    status_by_id = {str(row["evaluator_id"]): row["status"] for row in rows}
    assert status_by_id["requirement_coverage"] == "failed"
    assert status_by_id["task_completion"] == "failed"
    cases = [
        item
        for item in store.list_learning_cases(owner_principal_id=None)
        if item["case_key"] == f"run-{run.id}"
    ]
    assert cases and cases[0]["root_cause_class"] == "coverage_failure"
    candidates = store.list_improvement_candidates(owner_principal_id=None)
    candidate = next(item for item in candidates if item["candidate_type"] == "coverage_policy")
    job = store._session.scalar(  # noqa: SLF001 - integration assertion on durable queue
        select(LearningExperimentJobRow).where(
            LearningExperimentJobRow.candidate_id == candidate["id"]
        )
    )
    assert job is not None and job.status == "pending"
    assert (
        store.get_active_learning_policy(
            policy_key="global.corrective_research",
            owner_principal_id=None,
        )
        == active_before
    )
