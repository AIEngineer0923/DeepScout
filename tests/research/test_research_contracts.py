"""Tests for research contracts, source authority, coverage, and final report."""

from __future__ import annotations

import pytest
from deepscout_core.domain.contracts import (
    EvidenceType,
    RequirementCoverageStatus,
    RequirementKind,
    SourceClass,
    SourceConstraintMode,
)
from deepscout_core.domain.enums import ClaimVerificationStatus
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
)
from deepscout_research.contracts.coverage import evaluate_coverage, gap_search_queries
from deepscout_research.contracts.evidence_relevance import (
    _explicit_identifiers,
    claim_specificity_allowed,
    is_evidence_relevant,
    is_search_result_relevant,
)
from deepscout_research.contracts.extract import build_research_contract, derive_report_contract
from deepscout_research.contracts.query_planning import route_preferred_vendor_query
from deepscout_research.contracts.requirement_attribution import attribute_requirements
from deepscout_research.contracts.source_authority import (
    classify_source_authority,
    enrich_search_query_with_policy,
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
        "Explain GPAI obligations under the EU AI Act. Use only official EU institutional sources."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    assert contract.source_constraints
    assert contract.source_constraints[0].mode == SourceConstraintMode.ONLY
    assert "europa.eu" in contract.source_constraints[0].values


def test_contract_does_not_treat_practical_or_impact_as_a_legal_act() -> None:
    goal = (
        "Compare LFP and high-nickel NMC battery chemistries, focusing on energy density "
        "and how pack engineering changes the practical trade-off and lifecycle impact. "
        "Prefer peer-reviewed work."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    comparison = next(item for item in contract.requirements if item.requirement_id == "R_compare")
    assert SourceClass.PRIMARY_LEGISLATION not in comparison.expected_source_classes


def test_contract_does_not_infer_simulation_or_meta_analysis_from_ai_models_and_peer_reviewed() -> (
    None
):
    goal = (
        "Explain obligations for general-purpose AI models. "
        "Use only official EU institutional sources and prefer peer-reviewed context."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    material = [
        item for item in contract.requirements if item.requirement_id not in {"R0", "R_success"}
    ]
    assert all(
        EvidenceType.MODEL_SIMULATION not in item.required_evidence_types for item in material
    )
    assert all(
        EvidenceType.REVIEW_META_ANALYSIS not in item.required_evidence_types for item in material
    )


def test_contract_models_source_only_and_plan_order_as_structural_requirements() -> None:
    goal = (
        "Identify the office holder. The second task must depend on the first task. "
        "Use only official EU institutional sources."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    kinds = {item.text: item.kind for item in contract.requirements}
    assert kinds["The second task must depend on the first task."] == RequirementKind.DEPENDENCY
    assert kinds["Use only official EU institutional sources."] == RequirementKind.SOURCE_POLICY


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
    pmc = classify_source_authority(url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12466332/")
    assert pmc.source_class == SourceClass.PEER_REVIEWED


def test_evidence_relevance_rejects_noise() -> None:
    goal = "EU AI Act GPAI obligations"
    assert not is_evidence_relevant(
        quote="Morrisons supermarket debt restructuring announcement",
        query="GPAI obligations",
        goal=goal,
    )


def test_explicit_identifier_detection_is_linear_and_bounded() -> None:
    assert _explicit_identifiers("Compare GraphRAG with LFP and ordinary words") == {
        "graphrag",
        "lfp",
    }
    assert _explicit_identifiers("A" * 100_000) == set()


def test_search_result_relevance_rejects_unrelated_authoritative_result() -> None:
    goal = (
        "Compare hybrid RAG, GraphRAG, and long-context retrieval architectures for a "
        "production knowledge assistant in 2026."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    assert not is_search_result_relevant(
        title="Prospective evaluation of COMPOSER-LLM in the emergency department",
        snippet="Clinical documentation and medication alerts were evaluated for new patients.",
        query="RAG architecture evaluation methodology peer reviewed study",
        goal=goal,
        contract=contract,
    )
    assert is_search_result_relevant(
        title="From local to global: a graph RAG approach to query-focused summarization",
        snippet="GraphRAG combines graph indexing and retrieval for global questions.",
        query="GraphRAG retrieval architecture original paper",
        goal=goal,
        contract=contract,
    )
    assert not is_search_result_relevant(
        title="Thinking about context in AI",
        snippet="Context windows influence how a language model responds.",
        query="Long-context LLM retrieval architectures",
        goal=goal,
        contract=contract,
    )


def test_evidence_relevance_requires_quote_to_name_research_subject() -> None:
    goal = (
        "Compare hybrid RAG, GraphRAG, and long-context retrieval architectures for a "
        "production knowledge assistant in 2026."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    assert not is_evidence_relevant(
        quote=(
            "Methods Study Design and Evaluation of COMPOSER-LLM in the ED We conducted "
            "a prospective observational evaluation of clinical alerts."
        ),
        query="architecture evaluation strategy peer reviewed study methods results",
        goal=goal,
        contract=contract,
    )
    assert is_evidence_relevant(
        quote=(
            "A RAG pipeline consists of a retriever that obtains additional context and a "
            "generator that produces the answer."
        ),
        query="RAG retrieval architecture evaluation",
        goal=goal,
        contract=contract,
    )


def test_evidence_relevance_accepts_strong_cross_language_context() -> None:
    goal = "Valuta se l'arretramento gestito riduce il rischio di alluvioni costiere."
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    assert is_evidence_relevant(
        quote=(
            "Observed managed retreat outcomes reduced long-term coastal flood losses "
            "in the studied communities."
        ),
        query=(
            "Valuta l'arretramento gestito. Managed retreat observed outcomes "
            "long-term coastal flood losses."
        ),
        goal=goal,
        contract=contract,
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


def test_three_way_comparison_and_technical_source_policy_are_extracted() -> None:
    goal = (
        "Compare hybrid RAG, GraphRAG, and long-context retrieval architectures for a "
        "production assistant. Prefer original papers and official framework or vendor "
        "documentation."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    comparison = next(item for item in contract.requirements if item.requirement_id == "R_compare")
    assert comparison.comparison_subjects == [
        "hybrid RAG",
        "GraphRAG",
        "long-context retrieval architectures",
    ]
    assert SourceClass.PEER_REVIEWED in contract.preferred_source_classes
    assert SourceClass.SOFTWARE_VENDOR in contract.preferred_source_classes
    for statement in (
        "Hybrid RAG combines sparse and dense retrieval with reranking.",
        "Graph RAG creates entity graphs and community summaries.",
        "Long-context retrieval uses a large context window and prompt caching.",
    ):
        assert "R_compare" in attribute_requirements(
            statement=statement,
            quote=statement,
            contract=contract,
        )


def test_two_way_evidence_comparison_extracts_named_subjects() -> None:
    goal = (
        "Compare the current evidence on LFP and high-nickel NMC battery chemistries for "
        "passenger EVs, focusing on cycle life and energy density."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    comparison = next(item for item in contract.requirements if item.requirement_id == "R_compare")
    assert comparison.comparison_subjects == [
        "LFP",
        "high-nickel NMC battery chemistries for passenger EVs",
    ]


def test_italian_comparison_does_not_treat_requested_metrics_as_subjects() -> None:
    goal = (
        "Confronta LFP e NMC ad alto contenuto di nichel su ciclo di vita, densità energetica, "
        "sicurezza termica, driver di costo ed effetti dell'ingegneria di pacco."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    comparison = next(item for item in contract.requirements if item.requirement_id == "R_compare")
    assert comparison.comparison_subjects == ["LFP", "NMC ad alto contenuto di nichel"]


def test_official_domain_matching_uses_domain_boundaries() -> None:
    assert (
        classify_source_authority(
            url="https://dataintelo.com/report/example",
            title="Market report",
        ).source_class
        == SourceClass.UNKNOWN
    )
    assert (
        classify_source_authority(
            url="https://www.nist.gov/report/example",
            title="NIST report",
        ).source_class
        == SourceClass.OFFICIAL_INSTITUTIONAL
    )


def test_classify_official_software_vendor_documentation() -> None:
    meta = classify_source_authority(
        url="https://microsoft.github.io/graphrag/query/overview/",
        title="GraphRAG query engine",
    )
    assert meta.source_class == SourceClass.SOFTWARE_VENDOR
    assert meta.authority_class.value == "primary"


def test_preferred_vendor_query_routes_architecture_tasks_to_primary_docs() -> None:
    goal = (
        "Compare hybrid RAG, GraphRAG, and long-context retrieval architectures. "
        "Prefer original papers and official vendor documentation."
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    assert route_preferred_vendor_query(
        "Analyze GraphRAG community summaries and local search",
        contract,
    ).startswith("site:learn.microsoft.com/en-us/agent-framework/integrations/")
    assert route_preferred_vendor_query(
        "Analyze long-context prompt caching and context windows",
        contract,
    ).startswith("site:ai.google.dev/gemini-api/docs/long-context")
    broad = "Compare hybrid RAG, GraphRAG, and long-context retrieval"
    assert route_preferred_vendor_query(broad, contract) == broad
    enriched = enrich_search_query_with_policy(
        route_preferred_vendor_query("Analyze GraphRAG local and global search", contract),
        contract,
    )
    assert enriched == (
        "site:learn.microsoft.com/en-us/agent-framework/integrations/by-component/"
        "context-providers/neo4j GraphRAG vector full-text hybrid retrieval "
        "official documentation"
    )


def test_preferred_scientific_query_routes_battery_tasks_to_primary_sources() -> None:
    goal = "Compare LFP and NMC for EVs. Prefer peer-reviewed work and national lab reports."
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    assert route_preferred_vendor_query(
        "Analyze LFP and NMC cathode material cost differences",
        contract,
    ).startswith("site:pmc.ncbi.nlm.nih.gov/articles/PMC12466332")
    assert route_preferred_vendor_query(
        "Compare LFP and NMC cycle life and thermal safety",
        contract,
    ).startswith("site:frontiersin.org/journals/chemistry")
    assert route_preferred_vendor_query(
        "Explain the LFP and NMC pack-level trade-off",
        contract,
    ).startswith("site:pmc.ncbi.nlm.nih.gov/articles/PMC12466332")


def test_tradeoff_attribution_accepts_scientific_contrast_language() -> None:
    goal = "Compare LFP and NMC batteries and explain the practical trade-off."
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    matched = attribute_requirements(
        statement=("NMC has higher energy density, whereas LFP has lower thermal runaway risk."),
        quote=(
            "NMC cells provide higher specific energy while LFP cells show greater thermal "
            "stability."
        ),
        contract=contract,
    )
    assert "R_tradeoff" in matched


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


@pytest.mark.postgres
def test_coverage_validates_dependency_requirements_against_the_executed_dag(
    store, settings
) -> None:
    goal = "Identify the office holder. The second task must depend on the first task."
    run = store.create_run(
        ResearchRunCreate(goal=goal, budget=settings.default_research_budget()),
        settings,
    )
    contract = build_research_contract(goal=goal, planner=_planner(goal))
    store.save_plan(
        run.id,
        ResearchPlanWrite(
            strategy="ordered",
            success_criteria="Run the dependent task after the prerequisite.",
            questions=[goal],
            tasks=[
                PlannerTask(task_key="identify", objective="Identify the office holder"),
                PlannerTask(
                    task_key="guidance",
                    objective="Research the dependent guidance",
                    depends_on=["identify"],
                ),
            ],
        ),
    )
    coverage = evaluate_coverage(store, run.id, contract)
    requirement_by_id = {
        requirement.requirement_id: requirement for requirement in contract.requirements
    }
    dependency_entries = [
        entry
        for entry in coverage.entries
        if requirement_by_id[entry.requirement_id].kind == RequirementKind.DEPENDENCY
    ]
    assert dependency_entries
    assert all(entry.status == RequirementCoverageStatus.SUPPORTED for entry in dependency_entries)
