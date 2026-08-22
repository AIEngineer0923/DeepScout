"""Retrieval regression closure — corpus semantics, pipeline gate, sanitizer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_evaluation.regression_origins import (
    RegressionOrigin,
    origin_metadata_for,
    validate_case_origins,
)
from deepscout_evaluation.retrieval_pipeline_gate import (
    evaluate_contextual_contract_cases,
    evaluate_rerank_cases,
    evaluate_rrf_cases,
    load_pipeline_fixture,
    run_pipeline_gate,
)
from deepscout_evaluation.retrieval_regression import (
    load_production_reviewed,
    load_regression_baseline,
    load_synthetic_regressions,
    run_deterministic_gate,
    validate_regression_fixture,
)
from deepscout_evaluation.retrieval_sanitizer import (
    contains_private_url,
    contains_secret_material,
    sanitize_regression_candidate,
    sanitize_text,
    sanitize_url,
    validate_fixture_privacy,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE, RETRIEVAL_ROUTER_ENABLED=True)


def test_corpus_manifest_exists() -> None:
    manifest = json.loads(
        Path("libs/evaluation/data/retrieval_corpus_manifest_v1.json").read_text()
    )
    ids = {c["id"] for c in manifest["corpora"]}
    assert "retrieval-synthetic-regressions-v1" in ids
    assert "retrieval-pipeline-deterministic-v1" in ids
    assert "retrieval-production-reviewed-v1" in ids


def test_synthetic_corpus_semantics() -> None:
    fixture = load_synthetic_regressions()
    assert fixture["corpus_type"] == "synthetic_regression"
    assert fixture["version"] == "retrieval-synthetic-regressions-v1"
    errors = validate_regression_fixture(fixture)
    assert errors == []


def test_production_reviewed_empty() -> None:
    reviewed = load_production_reviewed()
    assert reviewed["corpus_type"] == "production_reviewed"
    assert reviewed["cases"] == []
    assert validate_regression_fixture(reviewed) == []


def test_origin_taxonomy_production_candidate_not_ci() -> None:
    meta = origin_metadata_for(RegressionOrigin.PRODUCTION_CANDIDATE)
    assert meta.safe_to_commit is False
    case_stub = {
        "case_id": "x",
        "origin": "production_candidate",
        "query": "q",
        "language": "en",
        "domain": "d",
    }
    errors = validate_case_origins([case_stub], corpus_type="synthetic_regression")
    assert errors


def test_origin_production_reviewed_requires_reviewed_origin() -> None:
    reviewed_stub = {
        "case_id": "x",
        "origin": "development_synthetic",
        "query": "q",
        "language": "en",
        "domain": "d",
    }
    errors = validate_case_origins([reviewed_stub], corpus_type="production_reviewed")
    assert any("production_reviewed" in e for e in errors)


def test_baseline_v2_references_corpora() -> None:
    baseline = load_regression_baseline()
    assert baseline["version"] == "retrieval-regression-baseline-v2"
    assert "pipeline_critical_cases" in baseline
    assert "changelog" in baseline


def test_rrf_fixture_cases() -> None:
    fixture = load_pipeline_fixture()
    results = evaluate_rrf_cases(fixture["rrf_cases"])
    assert all(r.passed for r in results)


def test_rerank_fixture_cases() -> None:
    fixture = load_pipeline_fixture()
    results = evaluate_rerank_cases(fixture["rerank_cases"])
    assert all(r.passed for r in results)


def test_contextual_contract_cases() -> None:
    fixture = load_pipeline_fixture()
    results = evaluate_contextual_contract_cases(fixture["contextual_contract_cases"])
    assert all(r.passed for r in results)


@pytest.mark.postgres
def test_pipeline_gate_passes(store, settings, db_session) -> None:
    baseline = load_regression_baseline()
    report = run_pipeline_gate(
        settings=settings, store=store, db_session=db_session, baseline=baseline
    )
    assert report.passed, report.policy_violations


@pytest.mark.postgres
def test_full_deterministic_gate_passes(store, settings, db_session) -> None:
    report = run_deterministic_gate(settings=settings, store=store, db_session=db_session)
    assert report.passed, report.policy_violations
    assert report.pipeline is not None
    assert report.pipeline.passed


def test_sanitizer_refuses_secrets() -> None:
    bearer = "Bearer " + ("a" * 30)
    assert contains_secret_material(bearer)
    with pytest.raises(ValueError):
        sanitize_regression_candidate({"query": bearer, "sanitized_notes": ""})


def test_sanitizer_redacts_email_and_uuid() -> None:
    text = sanitize_text("user@corp.com run 550e8400-e29b-41d4-a716-446655440000")
    assert "user@corp.com" not in text
    assert "550e8400" not in text


def test_sanitizer_private_urls() -> None:
    assert contains_private_url("https://foo.supabase.co/rest/v1")
    assert contains_private_url("http://localhost:5432/db")
    cleaned = sanitize_url("https://myapp.railway.app/internal?token=abc")
    assert "myapp.railway.app" not in cleaned
    assert "token" not in cleaned


def test_sanitizer_strips_tenant_fields() -> None:
    out = sanitize_regression_candidate(
        {
            "query": "battery regulation",
            "tenant_id": "t-1",
            "owner_principal_id": "p-1",
            "sanitized_notes": "ok",
        }
    )
    assert "tenant_id" not in out


def test_privacy_rejects_production_candidate_in_fixture() -> None:
    fixture = {
        "cases": [{"case_id": "x", "origin": "production_candidate", "query": "safe query"}]
    }
    violations = validate_fixture_privacy(fixture)
    assert violations


def test_ingest_preview_refuses_secrets() -> None:
    from scripts import retrieval_regression_ingest as ingest

    with pytest.raises(ValueError, match="secret|Refused"):
        ingest.sanitize_regression_candidate(
            {"query": "Bearer " + ("x" * 40), "sanitized_notes": ""}
        )
