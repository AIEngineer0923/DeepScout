"""Router quality — deterministic intent classification and confusion matrix."""

from __future__ import annotations

import pytest
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_evaluation.retrieval_quality import evaluate_router_cases, load_benchmark_v2
from deepscout_research.retrieval.planner import plan_retrieval_query
from deepscout_research.retrieval.router import classify_intent, route_retrieval


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE, RETRIEVAL_ROUTER_ENABLED=True)


@pytest.fixture
def benchmark() -> dict:
    return load_benchmark_v2()


def test_router_benchmark_accuracy(settings: Settings, benchmark: dict) -> None:
    result = evaluate_router_cases(benchmark["router_cases"], settings=settings)
    assert result["total"] == len(benchmark["router_cases"])
    assert result["accuracy"] >= 0.9, result["confusion_matrix"]


def test_router_confusion_matrix_shape(settings: Settings, benchmark: dict) -> None:
    result = evaluate_router_cases(benchmark["router_cases"], settings=settings)
    matrix = result["confusion_matrix"]
    for case in benchmark["router_cases"]:
        expected = case["expected_intent"]
        assert expected in matrix
        assert sum(matrix[expected].values()) >= 1


def test_long_context_skips_retrieval(settings: Settings) -> None:
    plan = plan_retrieval_query(
        query="summarize this short note",
        run_id=__import__("uuid").uuid4(),
        settings=settings,
        document_token_estimate=500,
    )
    assert plan.skip_retrieval is True
    assert classify_intent(plan).value == "long_context"
    route = route_retrieval(plan)
    assert route.skip_retrieval is True


def test_entity_relation_enables_graph(settings: Settings) -> None:
    plan = plan_retrieval_query(
        query="relationship between AlphaCells and FleetOperator Beta",
        run_id=__import__("uuid").uuid4(),
        settings=settings,
        document_token_estimate=5000,
    )
    route = route_retrieval(plan)
    assert classify_intent(plan).value == "entity_relation"
    assert route.use_graph is True
    assert route.use_compiled is True


def test_mixed_corpus_from_contradiction_hint(settings: Settings) -> None:
    plan = plan_retrieval_query(
        query="what contradicts mass-market commercialization in our sources",
        run_id=__import__("uuid").uuid4(),
        settings=settings,
        document_token_estimate=5000,
    )
    assert plan.corpus == "both"
    assert classify_intent(plan).value == "mixed"
    route = route_retrieval(plan)
    assert route.use_compiled is True
    assert route.use_graph is True


def test_compiled_corpus_maps_to_global_thematic(settings: Settings) -> None:
    plan = plan_retrieval_query(
        query="what have we learned about energy density from our research",
        run_id=__import__("uuid").uuid4(),
        settings=settings,
        document_token_estimate=5000,
    )
    assert plan.corpus == "compiled"
    assert classify_intent(plan).value == "global_thematic"


def test_semantic_not_mixed_without_both_hint(settings: Settings) -> None:
    plan = plan_retrieval_query(
        query="EU battery regulation effective date and carbon footprint",
        run_id=__import__("uuid").uuid4(),
        settings=settings,
        document_token_estimate=5000,
    )
    assert plan.corpus == "raw"
    assert classify_intent(plan).value == "semantic"


def test_identifier_single_entity_not_mixed(settings: Settings) -> None:
    plan = plan_retrieval_query(
        query="CVE-2024-1234 impact on solid-state battery safety",
        run_id=__import__("uuid").uuid4(),
        settings=settings,
        document_token_estimate=5000,
    )
    assert classify_intent(plan).value == "identifier"
    assert plan.corpus == "raw"


def test_quick_mode_scales_budget(settings: Settings) -> None:
    plan = plan_retrieval_query(
        query="CVE-2024-1234",
        run_id=__import__("uuid").uuid4(),
        settings=settings,
        document_token_estimate=5000,
    )
    standard = route_retrieval(plan, research_mode="standard")
    quick = route_retrieval(plan, research_mode="quick")
    assert quick.top_k <= standard.top_k
    assert quick.candidate_k <= standard.candidate_k
