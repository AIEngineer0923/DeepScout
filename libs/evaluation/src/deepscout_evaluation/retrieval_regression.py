"""Production-driven retrieval regression — deterministic CI gate and reporting."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from deepscout_core.settings import Settings
from deepscout_persistence.retrieval import list_chunks_for_run, replace_chunks
from deepscout_research.retrieval.bm25 import build_bm25_index
from deepscout_research.retrieval.chunking import chunk_snapshot_text
from deepscout_research.retrieval.models import RetrievedChunk
from deepscout_research.retrieval.planner import plan_retrieval_query
from deepscout_research.retrieval.router import classify_intent, route_retrieval
from deepscout_research.retrieval.security import looks_like_injection
from deepscout_research.retrieval.spec import CHUNKING_VERSION

from deepscout_evaluation.regression_origins import validate_case_origins
from deepscout_evaluation.retrieval_diagnostics import (
    RetrievalDiagnosticTrace,
    infer_retrieval_failure_class,
)
from deepscout_evaluation.retrieval_pipeline_gate import (
    PipelineGateReport,
    format_pipeline_report,
    load_pipeline_fixture,
    run_pipeline_gate,
)
from deepscout_evaluation.retrieval_quality import (
    AblationMode,
    _mean_metrics,
    evaluate_router_cases,
    run_ablation_retrieval,
    score_retrieved_chunks,
    seed_benchmark_corpus,
)
from deepscout_evaluation.retrieval_sanitizer import validate_fixture_privacy

SYNTHETIC_REGRESSIONS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "retrieval_synthetic_regressions_v1.json"
)
PRODUCTION_REVIEWED_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "retrieval_production_reviewed_v1.json"
)
PIPELINE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "retrieval_pipeline_deterministic_v1.json"
)
CORPUS_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "retrieval_corpus_manifest_v1.json"
)
# Backward-compatible alias (deprecated name)
PRODUCTION_REGRESSIONS_PATH = SYNTHETIC_REGRESSIONS_PATH
REGRESSION_BASELINE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "retrieval_regression_baseline_v2.json"
)

REQUIRED_CASE_FIELDS = ("case_id", "query", "origin", "language", "domain")


@dataclass
class RegressionCaseResult:
    case_id: str
    passed: bool
    router_pass: bool | None = None
    bm25_hit_at_3: float | None = None
    expected_intent: str | None = None
    actual_intent: str | None = None
    failure_class: str | None = None
    inferred_failure_class: str | None = None
    critical: bool = False
    reasons: list[str] = field(default_factory=list)


@dataclass
class RegressionGateReport:
    corpus_version: str
    baseline_version: str
    passed: bool
    total_cases: int
    passed_cases: int
    failed_cases: int
    critical_failures: list[str] = field(default_factory=list)
    router: dict[str, Any] = field(default_factory=dict)
    retrieval: dict[str, Any] = field(default_factory=dict)
    ablation: dict[str, Any] = field(default_factory=dict)
    by_domain: dict[str, Any] = field(default_factory=dict)
    by_language: dict[str, Any] = field(default_factory=dict)
    failure_classes: dict[str, int] = field(default_factory=dict)
    case_results: list[RegressionCaseResult] = field(default_factory=list)
    policy_violations: list[str] = field(default_factory=list)
    privacy_violations: list[str] = field(default_factory=list)
    pipeline: PipelineGateReport | None = None
    production_reviewed_cases: int = 0


def load_production_regressions(path: Path | None = None) -> dict[str, Any]:
    """Deprecated alias — loads synthetic regression corpus."""
    return load_synthetic_regressions(path)


def load_synthetic_regressions(path: Path | None = None) -> dict[str, Any]:
    target = path or SYNTHETIC_REGRESSIONS_PATH
    return json.loads(target.read_text())


def load_production_reviewed(path: Path | None = None) -> dict[str, Any]:
    target = path or PRODUCTION_REVIEWED_PATH
    return json.loads(target.read_text())


def load_regression_baseline(path: Path | None = None) -> dict[str, Any]:
    target = path or REGRESSION_BASELINE_PATH
    return json.loads(target.read_text())


def validate_regression_fixture(fixture: dict[str, Any]) -> list[str]:
    """Return schema/privacy validation errors."""
    errors: list[str] = []
    if "version" not in fixture:
        errors.append("missing version")
    if "cases" not in fixture:
        errors.append("missing cases")
        return errors
    seen: set[str] = set()
    for case in fixture.get("cases", []):
        for field_name in REQUIRED_CASE_FIELDS:
            if field_name not in case:
                errors.append(f"{case.get('case_id', '?')}: missing {field_name}")
        case_id = case.get("case_id")
        if case_id in seen:
            errors.append(f"duplicate case_id: {case_id}")
        if case_id:
            seen.add(case_id)
    errors.extend(validate_fixture_privacy(fixture))
    corpus_type = fixture.get("corpus_type", "synthetic_regression")
    errors.extend(validate_case_origins(fixture.get("cases", []), corpus_type=corpus_type))
    return errors


def index_documents_for_bm25(
    store,
    db_session,
    run_id: UUID,
) -> None:
    """Chunk snapshots without embedding calls — BM25/FTS deterministic gate."""
    snapshots = store.list_snapshots_for_run(run_id)
    for snapshot in snapshots:
        drafts = chunk_snapshot_text(snapshot.content_text, snapshot_id=str(snapshot.id))
        replace_chunks(
            db_session,
            run_id=run_id,
            source_id=snapshot.source_id,
            snapshot_id=snapshot.id,
            chunking_version=CHUNKING_VERSION,
            drafts=[
                {
                    "ordinal": item.ordinal,
                    "text": item.text,
                    "start_offset": item.start_offset,
                    "end_offset": item.end_offset,
                    "token_count": item.token_count,
                    "content_hash": item.content_hash,
                    "section_title": item.section_title,
                    "context_text": item.text,
                }
                for item in drafts
            ],
        )
    store.commit()


def bm25_retrieve_hits(
    db_session,
    *,
    run_id: UUID,
    query: str,
    top_k: int = 5,
    candidate_k: int = 20,
) -> list[RetrievedChunk]:
    chunk_rows = list_chunks_for_run(db_session, run_id=run_id)
    index = build_bm25_index([(row.id, row.context_text or row.text) for row in chunk_rows])
    ranked = index.search(query, limit=candidate_k)
    by_id = {row.id: row for row in chunk_rows}
    hits: list[RetrievedChunk] = []
    for rank, (chunk_id, score) in enumerate(ranked[:top_k], start=1):
        row = by_id.get(chunk_id)
        if row is None:
            continue
        hits.append(
            RetrievedChunk(
                chunk_id=row.id,
                snapshot_id=row.source_snapshot_id,
                source_id=row.source_id,
                run_id=row.research_run_id,
                text=row.text,
                locator=f"offset:{row.start_offset}-{row.end_offset}",
                ordinal=row.ordinal,
                start_offset=row.start_offset,
                end_offset=row.end_offset,
                bm25_rank=rank,
                bm25_score=score,
                fused_score=score,
                retrieval_reason="bm25:regression_gate",
                section_title=row.section_title,
            )
        )
    return hits


def _router_cases_from_fixture(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for case in fixture.get("cases", []):
        if "expected_intent" not in case:
            continue
        cases.append(
            {
                "id": case["case_id"],
                "query": case["query"],
                "expected_intent": case["expected_intent"],
                "document_token_estimate": case.get("document_token_estimate", 5000),
            }
        )
    for case in fixture.get("router_boundary_cases", []):
        cases.append(
            {
                "id": case["case_id"],
                "query": case["query"],
                "expected_intent": case["expected_intent"],
                "document_token_estimate": 5000,
            }
        )
    return cases


def evaluate_retrieval_case(
    *,
    case: dict[str, Any],
    hits: list[RetrievedChunk],
    source_to_doc: dict[UUID, str],
    settings: Settings,
) -> RegressionCaseResult:
    plan = plan_retrieval_query(
        query=case["query"],
        run_id=UUID(int=0),
        settings=settings,
        document_token_estimate=case.get("document_token_estimate", 5000),
    )
    route = route_retrieval(plan)
    actual_intent = classify_intent(plan).value
    expected_intent = case.get("expected_intent")
    router_pass = actual_intent == expected_intent if expected_intent else True

    metrics = score_retrieved_chunks(
        hits,
        source_to_doc=source_to_doc,
        relevant_doc_ids=case.get("relevant_doc_ids", []),
        relevant_phrases=case.get("relevant_phrases", []),
        k=5,
    )
    trace = RetrievalDiagnosticTrace.from_plan_and_hits(
        query=case["query"],
        plan=plan,
        route=route,
        hits=hits,
        source_to_doc=source_to_doc,
    )
    inferred = infer_retrieval_failure_class(case=case, trace=trace, metrics=metrics)

    reasons: list[str] = []
    passed = True
    if not router_pass:
        passed = False
        reasons.append(f"router expected {expected_intent}, got {actual_intent}")

    hit_at_3 = metrics.get("hit_at_3", metrics.get("hit_at_k", 0.0))
    should_answer = case.get("should_answer")
    should_retrieve = case.get("should_retrieve", should_answer)
    skip_retrieval = bool(case.get("skip_deterministic_retrieval"))

    if skip_retrieval:
        pass
    elif case.get("expect_injection_query"):
        if not looks_like_injection(case["query"]):
            passed = False
            reasons.append("query not flagged as injection")
        leak_k = case.get("credential_leak_check_top_k")
        if leak_k:
            leaked = any("api key" in h.text.lower() for h in hits[: int(leak_k)])
            if leaked:
                passed = False
                reasons.append("credential-like content in top results")
    elif not skip_retrieval:
        if should_retrieve is False and hit_at_3 > 0:
            passed = False
            reasons.append("no-answer case retrieved relevant material")
        elif should_answer is True and case.get("relevant_doc_ids") and hit_at_3 == 0:
            passed = False
            reasons.append("expected relevant doc not in top 3")

    irrelevant = case.get("irrelevant_doc_ids") or []
    if irrelevant and hits:
        top_doc = source_to_doc.get(hits[0].source_id)
        if top_doc in irrelevant:
            passed = False
            reasons.append(f"irrelevant doc ranked first: {top_doc}")

    return RegressionCaseResult(
        case_id=case["case_id"],
        passed=passed,
        router_pass=router_pass,
        bm25_hit_at_3=hit_at_3,
        expected_intent=expected_intent,
        actual_intent=actual_intent,
        failure_class=case.get("failure_class"),
        inferred_failure_class=inferred,
        critical=bool(case.get("critical")),
        reasons=reasons,
    )


def apply_regression_policy(
    *,
    case_results: list[RegressionCaseResult],
    baseline: dict[str, Any],
    router_accuracy: float,
) -> list[str]:
    """Explicit regression policy — critical case failures, not aggregate noise."""
    violations: list[str] = []
    min_router = float(baseline.get("router_accuracy_min", 0.95))
    if router_accuracy < min_router:
        violations.append(f"router accuracy {router_accuracy:.4f} below baseline min {min_router}")

    critical_expectations = baseline.get("critical_cases", {})
    by_id = {row.case_id: row for row in case_results}
    for case_id, expect in critical_expectations.items():
        row = by_id.get(case_id)
        if row is None:
            violations.append(f"critical case missing from run: {case_id}")
            continue
        if expect.get("router_pass") and row.router_pass is False:
            violations.append(f"{case_id}: router regression")
        if expect.get("skip_deterministic_retrieval"):
            continue
        bm25_min = expect.get("bm25_hit_at_3_min")
        if bm25_min is not None and (row.bm25_hit_at_3 or 0) < bm25_min:
            violations.append(
                f"{case_id}: bm25 hit@3 {row.bm25_hit_at_3} below min {bm25_min}"
            )
        bm25_max = expect.get("bm25_hit_at_3_max")
        if bm25_max is not None and (row.bm25_hit_at_3 or 0) > bm25_max:
            violations.append(
                f"{case_id}: bm25 hit@3 {row.bm25_hit_at_3} above max {bm25_max}"
            )
        if not row.passed and row.critical and not expect.get("skip_deterministic_retrieval"):
            violations.append(f"{case_id}: critical case failed ({'; '.join(row.reasons)})")
    return violations


def run_deterministic_gate(
    *,
    settings: Settings,
    store,
    db_session,
    fixture: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    include_ablation: bool = False,
    service=None,
    embedding_client=None,
    embedding_spec=None,
) -> RegressionGateReport:
    """CI-safe gate: router + BM25 on fixture corpus. No provider spend."""
    fixture = fixture or load_synthetic_regressions()
    baseline = baseline or load_regression_baseline()
    privacy_violations = validate_regression_fixture(fixture)

    reviewed = load_production_reviewed()
    reviewed_errors = validate_regression_fixture(reviewed)

    router_eval = evaluate_router_cases(
        _router_cases_from_fixture(fixture),
        settings=settings,
    )
    run, _, source_to_doc = seed_benchmark_corpus(
        store,
        settings,
        fixture["documents"],
        goal="retrieval-production-regression",
    )
    index_documents_for_bm25(store, db_session, run.id)

    case_results: list[RegressionCaseResult] = []
    per_query_metrics: list[dict[str, float]] = []
    failure_class_counts: dict[str, int] = defaultdict(int)
    by_domain: dict[str, list[bool]] = defaultdict(list)
    by_language: dict[str, list[bool]] = defaultdict(list)

    for case in fixture.get("cases", []):
        hits = bm25_retrieve_hits(
            db_session,
            run_id=run.id,
            query=case["query"],
            top_k=5,
            candidate_k=20,
        )
        result = evaluate_retrieval_case(
            case=case,
            hits=hits,
            source_to_doc=source_to_doc,
            settings=settings,
        )
        case_results.append(result)
        by_domain[case.get("domain", "unknown")].append(result.passed)
        by_language[case.get("language", "unknown")].append(result.passed)
        if result.inferred_failure_class:
            failure_class_counts[result.inferred_failure_class] += 1
        metrics = score_retrieved_chunks(
            hits,
            source_to_doc=source_to_doc,
            relevant_doc_ids=case.get("relevant_doc_ids", []),
            relevant_phrases=case.get("relevant_phrases", []),
            k=5,
        )
        per_query_metrics.append(metrics)

    policy_violations = apply_regression_policy(
        case_results=case_results,
        baseline=baseline,
        router_accuracy=float(router_eval["accuracy"]),
    )
    if privacy_violations:
        policy_violations.extend(privacy_violations)
    if reviewed_errors:
        policy_violations.extend([f"production_reviewed: {e}" for e in reviewed_errors])

    pipeline_report = run_pipeline_gate(
        settings=settings,
        store=store,
        db_session=db_session,
        fixture=load_pipeline_fixture(),
        baseline=baseline,
    )
    if not pipeline_report.passed:
        policy_violations.extend(pipeline_report.policy_violations)

    ablation: dict[str, Any] = {}
    if include_ablation and service is not None:
        ablation_cases = [
            {
                "id": c["case_id"],
                "query": c["query"],
                "relevant_doc_ids": c.get("relevant_doc_ids", []),
                "relevant_phrases": c.get("relevant_phrases", []),
            }
            for c in fixture.get("cases", [])
            if c.get("relevant_doc_ids")
        ]
        for mode in (AblationMode.BM25_ONLY, AblationMode.FULL_RRF_RERANK):
            rows: list[dict[str, float]] = []
            for case in ablation_cases:
                hits, _ = run_ablation_retrieval(
                    service,
                    session=db_session,
                    run_id=run.id,
                    query=case["query"],
                    mode=mode,
                    top_k=5,
                    candidate_k=20,
                    spec=embedding_spec,
                    client=embedding_client,
                )
                rows.append(
                    score_retrieved_chunks(
                        hits,
                        source_to_doc=source_to_doc,
                        relevant_doc_ids=case["relevant_doc_ids"],
                        relevant_phrases=case.get("relevant_phrases", []),
                        k=5,
                    )
                )
            ablation[mode.value] = _mean_metrics(rows)

    passed_cases = sum(1 for row in case_results if row.passed)
    failed_cases = len(case_results) - passed_cases
    critical_failures = [row.case_id for row in case_results if row.critical and not row.passed]

    return RegressionGateReport(
        corpus_version=fixture["version"],
        baseline_version=baseline["version"],
        passed=not policy_violations,
        total_cases=len(case_results),
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        critical_failures=critical_failures,
        router=router_eval,
        retrieval={"aggregate": _mean_metrics(per_query_metrics), "mode": "bm25_only"},
        ablation=ablation,
        by_domain={
            domain: {
                "passed": sum(1 for ok in rows if ok),
                "total": len(rows),
            }
            for domain, rows in by_domain.items()
        },
        by_language={
            lang: {
                "passed": sum(1 for ok in rows if ok),
                "total": len(rows),
            }
            for lang, rows in by_language.items()
        },
        failure_classes=dict(failure_class_counts),
        case_results=case_results,
        policy_violations=policy_violations,
        privacy_violations=privacy_violations,
        pipeline=pipeline_report,
        production_reviewed_cases=len(reviewed.get("cases", [])),
    )


def format_regression_report(report: RegressionGateReport) -> str:
    lines = [
        "DeepScout Retrieval Regression Gate",
        f"Synthetic corpus: {report.corpus_version}",
        f"Production-reviewed cases: {report.production_reviewed_cases}",
        f"Baseline: {report.baseline_version}",
        f"Status: {'PASS' if report.passed else 'FAIL'}",
        "",
        f"Cases: {report.passed_cases}/{report.total_cases} passed "
        f"({report.failed_cases} failed)",
    ]
    if report.critical_failures:
        lines.append(f"Critical failures: {', '.join(report.critical_failures)}")
    lines.extend(
        [
            "",
            "Router",
            f"  accuracy: {report.router.get('accuracy', 0):.4f} "
            f"({report.router.get('correct', 0)}/{report.router.get('total', 0)})",
        ]
    )
    matrix = report.router.get("confusion_matrix", {})
    if matrix:
        lines.append("  confusion matrix:")
        for expected, actuals in sorted(matrix.items()):
            for actual, count in sorted(actuals.items()):
                lines.append(f"    {expected} -> {actual}: {count}")

    agg = report.retrieval.get("aggregate", {})
    if agg:
        lines.extend(
            [
                "",
                f"Retrieval ({report.retrieval.get('mode', 'bm25_only')}) aggregate:",
                f"  hit@1={agg.get('hit_at_1', 0):.4f} "
                f"hit@3={agg.get('hit_at_3', 0):.4f} "
                f"mrr={agg.get('mrr', 0):.4f} "
                f"ndcg@5={agg.get('ndcg_at_k', 0):.4f}",
            ]
        )

    if report.by_language:
        lines.append("")
        lines.append("By language:")
        for lang, stats in sorted(report.by_language.items()):
            lines.append(f"  {lang}: {stats['passed']}/{stats['total']}")

    if report.failure_classes:
        lines.append("")
        lines.append("Failure class hints:")
        for cls, count in sorted(report.failure_classes.items()):
            lines.append(f"  {cls}: {count}")

    if report.policy_violations:
        lines.append("")
        lines.append("Policy violations:")
        for item in report.policy_violations:
            lines.append(f"  - {item}")

    if report.pipeline:
        lines.append("")
        lines.append(format_pipeline_report(report.pipeline))

    failed = [row for row in report.case_results if not row.passed]
    if failed:
        lines.append("")
        lines.append("Failed cases:")
        for row in failed:
            lines.append(
                f"  - {row.case_id}: {', '.join(row.reasons) or 'policy failure'}"
            )
    return "\n".join(lines)


def report_to_dict(report: RegressionGateReport) -> dict[str, Any]:
    return {
        "corpus_version": report.corpus_version,
        "baseline_version": report.baseline_version,
        "passed": report.passed,
        "total_cases": report.total_cases,
        "passed_cases": report.passed_cases,
        "failed_cases": report.failed_cases,
        "critical_failures": report.critical_failures,
        "router": report.router,
        "retrieval": report.retrieval,
        "ablation": report.ablation,
        "by_domain": report.by_domain,
        "by_language": report.by_language,
        "failure_classes": report.failure_classes,
        "policy_violations": report.policy_violations,
        "privacy_violations": report.privacy_violations,
        "production_reviewed_cases": report.production_reviewed_cases,
        "pipeline": {
            "version": report.pipeline.version,
            "passed": report.pipeline.passed,
            "policy_violations": report.pipeline.policy_violations,
        }
        if report.pipeline
        else None,
        "cases": [
            {
                "case_id": row.case_id,
                "passed": row.passed,
                "router_pass": row.router_pass,
                "bm25_hit_at_3": row.bm25_hit_at_3,
                "expected_intent": row.expected_intent,
                "actual_intent": row.actual_intent,
                "failure_class": row.failure_class,
                "inferred_failure_class": row.inferred_failure_class,
                "critical": row.critical,
                "reasons": row.reasons,
            }
            for row in report.case_results
        ],
    }
