"""Production retrieval regression — schema, sanitizer, gate, ingest."""

from __future__ import annotations

import pytest
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_evaluation.retrieval_diagnostics import (
    RetrievalDiagnosticTrace,
    infer_retrieval_failure_class,
)
from deepscout_evaluation.retrieval_regression import (
    apply_regression_policy,
    load_production_regressions,
    load_regression_baseline,
    run_deterministic_gate,
    validate_regression_fixture,
)
from deepscout_evaluation.retrieval_sanitizer import (
    contains_secret_material,
    sanitize_regression_candidate,
    sanitize_text,
    validate_fixture_privacy,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE, RETRIEVAL_ROUTER_ENABLED=True)


def test_production_regression_fixture_validates() -> None:
    fixture = load_production_regressions()
    errors = validate_regression_fixture(fixture)
    assert errors == []
    assert len(fixture["cases"]) >= 10


def test_baseline_matches_corpus() -> None:
    fixture = load_production_regressions()
    baseline = load_regression_baseline()
    assert baseline["corpus_version"] == fixture["version"]
    critical = baseline["critical_cases"]
    fixture_ids = {case["case_id"] for case in fixture["cases"] if case.get("critical")}
    assert fixture_ids.issubset(set(critical.keys()))


def test_sanitizer_strips_secrets() -> None:
    bearer = "Bearer " + ("a" * 26)
    assert contains_secret_material(bearer)
    cleaned = sanitize_text("contact user@example.com for keys")
    assert "user@example.com" not in cleaned
    fake_sk = "sk-" + ("a" * 24)
    with pytest.raises(ValueError, match="secret"):
        sanitize_regression_candidate({"query": fake_sk})


def test_sanitizer_removes_tenant_fields() -> None:
    candidate = {
        "query": "battery regulation",
        "tenant_id": "t-1",
        "owner_principal_id": "p-1",
        "sanitized_notes": "ok",
    }
    out = sanitize_regression_candidate(candidate)
    assert "tenant_id" not in out
    assert "owner_principal_id" not in out


def test_infer_routing_failure() -> None:
    trace = RetrievalDiagnosticTrace(
        query="q",
        detected_intent="semantic",
    )
    inferred = infer_retrieval_failure_class(
        case={"expected_intent": "identifier"},
        trace=trace,
        metrics={"hit_at_3": 1.0},
    )
    assert inferred == "routing_failure"


def test_infer_no_answer_false_positive() -> None:
    trace = RetrievalDiagnosticTrace(query="q", detected_intent="semantic")
    inferred = infer_retrieval_failure_class(
        case={"should_answer": False},
        trace=trace,
        metrics={"hit_at_3": 1.0},
    )
    assert inferred == "no_answer_false_positive"


def test_apply_regression_policy_critical_router() -> None:
    from deepscout_evaluation.retrieval_regression import RegressionCaseResult

    baseline = load_regression_baseline()
    violations = apply_regression_policy(
        case_results=[
            RegressionCaseResult(
                case_id="reg-en-cve-identifier",
                passed=False,
                router_pass=False,
                bm25_hit_at_3=1.0,
                critical=True,
                reasons=["router"],
            )
        ],
        baseline=baseline,
        router_accuracy=1.0,
    )
    assert any("router regression" in v for v in violations)


@pytest.mark.postgres
def test_deterministic_gate_passes(store, settings, db_session) -> None:
    report = run_deterministic_gate(settings=settings, store=store, db_session=db_session)
    assert report.total_cases > 0
    assert report.router["accuracy"] >= 0.9
    if report.policy_violations:
        pytest.fail("policy violations: " + "; ".join(report.policy_violations))


def test_ingest_preview_refuses_secrets() -> None:
    from scripts import retrieval_regression_ingest as ingest

    with pytest.raises(ValueError, match="secret|Refused"):
        ingest.sanitize_regression_candidate(
            {"query": "Bearer " + ("x" * 40), "sanitized_notes": ""}
        )


def test_privacy_validation_blocks_unsanitized_origin() -> None:
    fixture = {
        "cases": [{"case_id": "x", "origin": "production_unsanitized", "query": "q"}]
    }
    violations = validate_fixture_privacy(fixture)
    assert any("production_unsanitized" in v for v in violations)
