from deepscout_core.domain.contracts import AnswerRequirement, RequirementKind
from deepscout_core.domain.research_profiles import research_profile
from deepscout_research.contracts.deliverables import (
    infer_deliverable_spec,
    validate_report_deliverable,
)
from deepscout_research.contracts.numeric_constraints import extract_numeric_constraints
from deepscout_research.followup import classify_followup


def test_allocation_contract_extracts_generic_quotas_and_conflicting_budgets() -> None:
    goal = (
        "Costruisci una lista con budget 1000 crediti. Alla fine proponi "
        "3 portieri, 8 difensori, 8 centrocampisti e 6 attaccanti, con budget "
        "massimo assegnato a ciascuno e totale esattamente compatibile con 500 crediti."
    )
    constraints, conflicts = extract_numeric_constraints(goal)
    spec = infer_deliverable_spec(
        goal=goal,
        requirements=[
            AnswerRequirement(
                requirement_id="R1",
                text="Confronta rendimento, rischio e costo di ogni candidato",
                kind=RequirementKind.COMPARISON,
            )
        ],
        numeric_constraints=constraints,
    )

    assert spec.kind.value == "allocation"
    assert spec.exact_item_count == 25
    assert [item.exact_count for item in spec.category_quotas] == [3, 8, 8, 6]
    assert spec.budget_total == "500"
    assert conflicts == ["budget_total: 1000, 500 crediti"]
    assert spec.attribute_goals[0].requirement_ids == ["R1"]


def test_report_deliverable_validator_checks_rows_quotas_and_budget() -> None:
    goal = "Scegli 2 laptop e 1 tablet con budget totale 900 EUR"
    constraints, _ = extract_numeric_constraints(goal)
    spec = infer_deliverable_spec(goal=goal, requirements=[], numeric_constraints=constraints)
    body = """## Recommendation

| Name | Category | Cost | Confidence |
| --- | --- | ---: | --- |
| Alpha | Laptop | 300 | high |
| Beta | Laptop | 350 | medium |
| Gamma | Tablet | 250 | medium |
| Total |  | 900 |  |
"""
    result = validate_report_deliverable(body, spec)

    assert result.valid
    assert result.observed["item_count"] == 3
    assert result.observed["budget_total"] == 900.0
    assert result.observed["category_counts"] == {"laptop": 2, "tablet": 1}


def test_report_deliverable_validator_rejects_prose_only_claim_of_completeness() -> None:
    constraints, _ = extract_numeric_constraints("budget totale 100 EUR")
    spec = infer_deliverable_spec(
        goal="Scegli 2 prodotti con budget totale 100 EUR",
        requirements=[],
        numeric_constraints=constraints,
    )

    result = validate_report_deliverable("I selected two products within budget.", spec)

    assert not result.valid
    assert result.issues == ["deliverable_table_missing"]


def test_technical_build_requirement_remains_a_narrative_deliverable() -> None:
    spec = infer_deliverable_spec(
        goal=(
            "Explain Python free-threading, including experimental status, "
            "build requirements, startup flags, limitations, and GIL impact."
        ),
        requirements=[],
        numeric_constraints=[],
    )

    assert spec.kind.value == "narrative"


def test_imperative_build_still_requests_a_structured_deliverable() -> None:
    spec = infer_deliverable_spec(
        goal="Build a portfolio with a total budget of 500 EUR.",
        requirements=[],
        numeric_constraints=[],
    )

    assert spec.kind.value == "portfolio"


def test_quick_profile_is_one_task_and_followups_have_explicit_intent() -> None:
    assert research_profile("quick").max_requirement_tasks == 1
    assert classify_followup("Find newer evidence published this month") == "freshness"
    assert classify_followup("Why do these sources disagree?") == "contradiction"
    assert classify_followup("Exclude Alpha and keep the budget below 500") == "constraint_change"
    assert classify_followup("Explain the strongest claim in more detail") == "deeper"
