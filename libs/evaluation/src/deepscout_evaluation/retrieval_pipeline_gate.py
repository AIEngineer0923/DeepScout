"""Deterministic full-pipeline regression gate — frozen vectors, no provider spend."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from deepscout_core.settings import Settings
from deepscout_persistence.retrieval import list_chunks_for_run, persist_embeddings, replace_chunks
from deepscout_research.retrieval.chunking import chunk_snapshot_text
from deepscout_research.retrieval.contextual import build_context_text
from deepscout_research.retrieval.fusion import reciprocal_rank_fusion
from deepscout_research.retrieval.models import RetrievalQuery, RetrievedChunk
from deepscout_research.retrieval.planner import plan_retrieval_query
from deepscout_research.retrieval.rerank import rerank_candidates
from deepscout_research.retrieval.router import classify_intent
from deepscout_research.retrieval.service import RetrievalService
from deepscout_research.retrieval.spec import (
    CHUNKING_VERSION,
    EMBEDDING_CONFIG_VERSION,
    EmbeddingSpec,
)

from deepscout_evaluation.retrieval_quality import (
    evaluate_compiled_retrieval,
    evaluate_graph_retrieval,
    seed_benchmark_corpus,
    seed_compiled_fixture,
    seed_graph_fixture,
)

PIPELINE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "retrieval_pipeline_deterministic_v1.json"
)
_CHUNK_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def chunk_key_uuid(key: str) -> UUID:
    return uuid.uuid5(_CHUNK_NS, key)


def load_pipeline_fixture(path: Path | None = None) -> dict[str, Any]:
    target = path or PIPELINE_FIXTURE_PATH
    return json.loads(target.read_text())


@dataclass
class PipelineCaseResult:
    case_id: str
    stage: str
    passed: bool
    critical: bool
    failure_class: str | None = None
    reasons: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineGateReport:
    version: str
    passed: bool
    rrf: list[PipelineCaseResult] = field(default_factory=list)
    rerank: list[PipelineCaseResult] = field(default_factory=list)
    pipeline: list[PipelineCaseResult] = field(default_factory=list)
    contextual: list[PipelineCaseResult] = field(default_factory=list)
    compiled: list[PipelineCaseResult] = field(default_factory=list)
    graph: list[PipelineCaseResult] = field(default_factory=list)
    policy_violations: list[str] = field(default_factory=list)


def _rrf_contributions(
    ranked_lists: dict[str, list[str]], *, k: int = 60
) -> dict[str, float]:
    list_names = ("bm25_ranked", "fts_ranked", "dense_ranked")
    lists = [ranked_lists[name] for name in list_names if ranked_lists.get(name)]
    uuid_lists = [[chunk_key_uuid(key) for key in lst] for lst in lists]
    return reciprocal_rank_fusion(uuid_lists, k=k)


def evaluate_rrf_cases(cases: list[dict[str, Any]]) -> list[PipelineCaseResult]:
    results: list[PipelineCaseResult] = []
    for case in cases:
        ranked = {
            "bm25_ranked": case.get("bm25_ranked", []),
            "fts_ranked": case.get("fts_ranked", []),
            "dense_ranked": case.get("dense_ranked", []),
        }
        fused = _rrf_contributions(ranked)
        top_key = None
        if fused:
            top_uuid = max(fused, key=fused.get)
            for key in {k for lst in ranked.values() for k in lst}:
                if chunk_key_uuid(key) == top_uuid:
                    top_key = key
                    break
        expected = case.get("expected_top")
        passed = top_key == expected
        reasons: list[str] = []
        if not passed:
            reasons.append(f"expected top {expected}, got {top_key}")
        contributions = {
            key: round(fused.get(chunk_key_uuid(key), 0.0), 6)
            for key in {k for lst in ranked.values() for k in lst}
        }
        results.append(
            PipelineCaseResult(
                case_id=case["case_id"],
                stage="rrf",
                passed=passed,
                critical=bool(case.get("critical")),
                failure_class=case.get("failure_class") if not passed else None,
                reasons=reasons,
                diagnostics={
                    "bm25_ranked": ranked["bm25_ranked"],
                    "fts_ranked": ranked["fts_ranked"],
                    "dense_ranked": ranked["dense_ranked"],
                    "rrf_scores": contributions,
                    "fused_top": top_key,
                },
            )
        )
    return results


def _make_chunk(
    *,
    key: str,
    text: str,
    source_key: str,
    fused_score: float,
    run_id: UUID,
) -> RetrievedChunk:
    source_id = chunk_key_uuid(f"source:{source_key}")
    return RetrievedChunk(
        chunk_id=chunk_key_uuid(key),
        snapshot_id=chunk_key_uuid(f"snap:{key}"),
        source_id=source_id,
        run_id=run_id,
        text=text,
        locator=f"test:{key}",
        ordinal=0,
        start_offset=0,
        end_offset=len(text),
        fused_score=fused_score,
    )


def evaluate_rerank_cases(cases: list[dict[str, Any]]) -> list[PipelineCaseResult]:
    results: list[PipelineCaseResult] = []
    run_id = UUID(int=0)
    for case in cases:
        candidates = [
            _make_chunk(
                key=item["key"],
                text=item["text"],
                source_key=item["source"],
                fused_score=float(item["fused_score"]),
                run_id=run_id,
            )
            for item in case["candidates"]
        ]
        reranked = rerank_candidates(
            candidates,
            query=case["query"],
            max_per_source=int(case.get("max_per_source", 2)),
            limit=len(candidates),
        )
        top_key = None
        for item in reranked:
            for cand in case["candidates"]:
                if chunk_key_uuid(cand["key"]) == item.chunk_id:
                    top_key = cand["key"]
                    break
            if top_key:
                break
        expected_top = case["expected_top"]
        passed = top_key == expected_top
        reasons: list[str] = []
        if not passed:
            reasons.append(f"expected top {expected_top}, got {top_key}")
        second_key = None
        if case.get("expected_second") and len(reranked) > 1:
            for cand in case["candidates"]:
                if chunk_key_uuid(cand["key"]) == reranked[1].chunk_id:
                    second_key = cand["key"]
            if second_key != case["expected_second"]:
                passed = False
                reasons.append(f"expected second {case['expected_second']}, got {second_key}")
        results.append(
            PipelineCaseResult(
                case_id=case["case_id"],
                stage="rerank",
                passed=passed,
                critical=bool(case.get("critical")),
                failure_class=case.get("failure_class") if not passed else None,
                reasons=reasons,
                diagnostics={
                    "query": case["query"],
                    "final_order": [
                        next(
                            c["key"]
                            for c in case["candidates"]
                            if chunk_key_uuid(c["key"]) == h.chunk_id
                        )
                        for h in reranked
                    ],
                    "rerank_scores": [h.rerank_score for h in reranked],
                },
            )
        )
    return results


class _DeterministicEmbeddings:
    """Frozen vectors — tests pipeline logic, not provider semantic quality."""

    def __init__(self, *, dimensions: int = 768) -> None:
        self.dimensions = dimensions

    def embed_query(self, query: str) -> list[float]:
        del query
        vec = [0.0] * self.dimensions
        vec[0] = 1.0
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimensions for _ in texts]


def _seed_doc_embeddings(
    db_session,
    *,
    run_id: UUID,
    rows: list,
    doc_seeds: dict[str, float],
    source_to_doc: dict[UUID, str],
    spec: EmbeddingSpec,
) -> None:
    items: list[tuple[UUID, list[float]]] = []
    for row in rows:
        doc_id = source_to_doc.get(row.source_id, "")
        seed = doc_seeds.get(doc_id, 0.1)
        vec = [0.0] * spec.dimensions
        vec[0] = seed
        items.append((row.id, vec))
    persist_embeddings(
        db_session,
        run_id=run_id,
        provider=spec.provider,
        model=spec.model,
        dimensions=spec.dimensions,
        config_version=spec.config_version,
        items=items,
    )


def _index_pipeline_documents(
    store,
    db_session,
    *,
    run_id: UUID,
    documents: list[dict[str, Any]],
    source_to_doc: dict[str, UUID],
    spec: EmbeddingSpec,
) -> dict[str, float]:
    seeds: dict[str, float] = {}
    for doc in documents:
        seeds[doc["id"]] = float(doc.get("dense_seed", 0.1))
        source_id = source_to_doc[doc["id"]]
        snapshot = next(
            s for s in store.list_snapshots_for_run(run_id) if s.source_id == source_id
        )
        drafts = chunk_snapshot_text(doc["text"], snapshot_id=str(snapshot.id))
        replace_chunks(
            db_session,
            run_id=run_id,
            source_id=source_id,
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
                    "context_text": build_context_text(
                        chunk_text=item.text,
                        document_title=doc.get("title", ""),
                        section_title=item.section_title,
                        source_url=f"https://example.invalid/{doc['id']}",
                    ),
                }
                for item in drafts
            ],
        )
    store.commit()
    rev = {sid: did for did, sid in source_to_doc.items()}
    rows = list_chunks_for_run(db_session, run_id=run_id)
    _seed_doc_embeddings(
        db_session,
        run_id=run_id,
        rows=rows,
        doc_seeds=seeds,
        source_to_doc={row.source_id: rev[row.source_id] for row in rows},
        spec=spec,
    )
    store.commit()
    return seeds


def evaluate_pipeline_integration_cases(
    *,
    settings: Settings,
    store,
    db_session,
    cases: list[dict[str, Any]],
    client: _DeterministicEmbeddings | None = None,
    spec: EmbeddingSpec | None = None,
) -> list[PipelineCaseResult]:
    spec = spec or EmbeddingSpec(
        provider="deterministic",
        model="frozen-fixture",
        dimensions=768,
        config_version=EMBEDDING_CONFIG_VERSION,
    )
    client = client or _DeterministicEmbeddings(dimensions=spec.dimensions)
    service = RetrievalService(store, settings, client=client, spec=spec)
    results: list[PipelineCaseResult] = []

    for case in cases:
        run, doc_to_source, source_to_doc = seed_benchmark_corpus(
            store,
            settings,
            case["documents"],
            goal=f"pipeline-{case['case_id']}",
        )
        _index_pipeline_documents(
            store,
            db_session,
            run_id=run.id,
            documents=case["documents"],
            source_to_doc=doc_to_source,
            spec=spec,
        )
        hits = service.retrieve(
            RetrievalQuery(
                query=case["query"],
                run_id=run.id,
                top_k=3,
                candidate_k=10,
                apply_rerank=bool(case.get("apply_rerank", True)),
            )
        )
        top_doc = source_to_doc.get(hits[0].source_id) if hits else None
        expected = case.get("expected_top_doc")
        should_retrieve = case.get("should_retrieve", True)
        plan = plan_retrieval_query(
            query=case["query"],
            run_id=run.id,
            settings=settings,
            document_token_estimate=5000,
        )
        actual_intent = classify_intent(plan).value
        intent_ok = actual_intent == case.get("expected_intent", actual_intent)
        passed = True
        reasons: list[str] = []
        if not intent_ok:
            passed = False
            reasons.append(f"intent mismatch: expected {case.get('expected_intent')}")
        if should_retrieve:
            if top_doc != expected:
                passed = False
                reasons.append(f"expected top doc {expected}, got {top_doc}")
        elif should_retrieve is False:
            pass

        diag: dict[str, Any] = {
            "expected_intent": case.get("expected_intent"),
            "actual_intent": classify_intent(plan).value,
            "expected_top_doc": expected,
            "actual_top_doc": top_doc,
            "final_top_k": [
                {
                    "doc": source_to_doc.get(h.source_id),
                    "bm25_rank": h.bm25_rank,
                    "lexical_rank": h.lexical_rank,
                    "dense_rank": h.dense_rank,
                    "fused_score": h.fused_score,
                    "rerank_score": h.rerank_score,
                }
                for h in hits[:3]
            ],
        }
        results.append(
            PipelineCaseResult(
                case_id=case["case_id"],
                stage="pipeline",
                passed=passed,
                critical=bool(case.get("critical")),
                failure_class=case.get("failure_class") if not passed else None,
                reasons=reasons,
                diagnostics=diag,
            )
        )
    return results


def evaluate_contextual_contract_cases(cases: list[dict[str, Any]]) -> list[PipelineCaseResult]:
    results: list[PipelineCaseResult] = []
    for case in cases:
        ctx = build_context_text(
            chunk_text=case["chunk_text"],
            document_title=case.get("document_title", ""),
            section_title=case.get("section_title"),
            source_url=case.get("source_url", ""),
        )
        passed = True
        reasons: list[str] = []
        if case.get("expect_chunk_unchanged") and ctx.endswith(case["chunk_text"]) is False:
            passed = False
            reasons.append("context_text must include unchanged chunk tail")
        if case.get("expect_context_equals_chunk") and ctx != case["chunk_text"]:
            passed = False
            reasons.append("legacy fallback should equal raw chunk")
        for fragment in case.get("expect_context_contains", []):
            if fragment not in ctx:
                passed = False
                reasons.append(f"missing context fragment: {fragment}")
        if case["chunk_text"] not in ctx:
            passed = False
            reasons.append("chunk_text must appear in context_text")
        results.append(
            PipelineCaseResult(
                case_id=case["case_id"],
                stage="contextual_contract",
                passed=passed,
                critical=True,
                reasons=reasons,
                diagnostics={"context_text": ctx, "chunk_text": case["chunk_text"]},
            )
        )
    return results


def _query_spec(fixture: dict[str, Any], row_id: str) -> dict[str, Any]:
    return next(q for q in fixture["queries"] if q.get("case_id", q.get("id")) == row_id)


def evaluate_compiled_gate(
    *,
    settings: Settings,
    store,
    db_session,
    fixture: dict[str, Any],
    client: _DeterministicEmbeddings | None = None,
    spec: EmbeddingSpec | None = None,
) -> list[PipelineCaseResult]:
    del db_session
    client = client or _DeterministicEmbeddings()
    spec = spec or EmbeddingSpec(
        provider="deterministic",
        model="frozen-fixture",
        dimensions=768,
        config_version=EMBEDDING_CONFIG_VERSION,
    )
    from deepscout_research.retrieval.indexer import index_snapshots_for_run

    run, _ = seed_compiled_fixture(store, settings, fixture["documents"], fixture)
    index_snapshots_for_run(store, settings, run.id, client=client, spec=spec)
    store.commit()
    service = RetrievalService(store, settings, client=client, spec=spec)
    eval_out = evaluate_compiled_retrieval(service, run_id=run.id, fixture=fixture)
    results: list[PipelineCaseResult] = []
    for row in eval_out["cases"]:
        case_spec = _query_spec(fixture, row["id"])
        provenance_ok = True
        passed = bool(row["passed"])
        if case_spec.get("expect_provenance_kind") == "chunk":
            hits = service.retrieve(
                RetrievalQuery(
                    query=case_spec["query"],
                    run_id=run.id,
                    top_k=5,
                    candidate_k=10,
                    corpus=case_spec.get("corpus", "raw"),
                )
            )
            compiled_in_results = [h for h in hits if h.provenance_kind == "compiled"]
            provenance_ok = not compiled_in_results and bool(hits)
            passed = provenance_ok
        elif case_spec.get("expect_compiled_hit"):
            passed = bool(row["passed"])
        else:
            passed = bool(row["passed"])
        results.append(
            PipelineCaseResult(
                case_id=row["id"],
                stage="compiled",
                passed=passed,
                critical=bool(case_spec.get("critical")),
                failure_class="compiled_knowledge_failure" if not passed else None,
                reasons=[] if passed else ["compiled gate failed"],
                diagnostics=row,
            )
        )
    return results


def evaluate_graph_gate(
    *,
    settings: Settings,
    store,
    db_session,
    fixture: dict[str, Any],
) -> list[PipelineCaseResult]:
    run_id = seed_graph_fixture(store, db_session, settings, fixture)
    eval_out = evaluate_graph_retrieval(db_session, run_id=run_id, fixture=fixture)
    results: list[PipelineCaseResult] = []
    for row in eval_out["cases"]:
        case_spec = _query_spec(fixture, row["id"])
        results.append(
            PipelineCaseResult(
                case_id=row["id"],
                stage="graph",
                passed=bool(row["passed"]),
                critical=bool(case_spec.get("critical")),
                failure_class="graph_retrieval_failure" if not row["passed"] else None,
                diagnostics=row,
            )
        )
    return results


def apply_pipeline_baseline(
    *,
    all_results: list[PipelineCaseResult],
    baseline: dict[str, Any],
) -> list[str]:
    """Baseline documents expected critical cases; failures are reported separately."""
    del baseline
    return []


def run_pipeline_gate(
    *,
    settings: Settings,
    store,
    db_session,
    fixture: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
) -> PipelineGateReport:
    fixture = fixture or load_pipeline_fixture()
    baseline = baseline or {}

    rrf = evaluate_rrf_cases(fixture.get("rrf_cases", []))
    rerank = evaluate_rerank_cases(fixture.get("rerank_cases", []))
    pipeline = evaluate_pipeline_integration_cases(
        settings=settings,
        store=store,
        db_session=db_session,
        cases=fixture.get("pipeline_cases", []),
    )
    contextual = evaluate_contextual_contract_cases(fixture.get("contextual_contract_cases", []))
    compiled = evaluate_compiled_gate(
        settings=settings,
        store=store,
        db_session=db_session,
        fixture=fixture.get("compiled_fixture", {}),
    )
    graph = evaluate_graph_gate(
        settings=settings,
        store=store,
        db_session=db_session,
        fixture=fixture.get("graph_fixture", {}),
    )

    all_results = rrf + rerank + pipeline + contextual + compiled + graph
    violations: list[str] = []
    by_id = {r.case_id: r for r in all_results}
    for case_id, expect in baseline.get("pipeline_critical_cases", {}).items():
        row = by_id.get(case_id)
        if row is None:
            violations.append(f"pipeline critical case missing: {case_id}")
        elif expect.get("must_pass") and not row.passed:
            violations.append(
                f"{case_id}: critical {expect.get('stage', row.stage)} failure "
                f"({'; '.join(row.reasons)})"
            )
    for row in all_results:
        if row.critical and not row.passed:
            msg = (
                f"{row.case_id}: critical {row.stage} failure "
                f"({'; '.join(row.reasons)})"
            )
            if msg not in violations:
                violations.append(msg)

    return PipelineGateReport(
        version=fixture["version"],
        passed=not violations,
        rrf=rrf,
        rerank=rerank,
        pipeline=pipeline,
        contextual=contextual,
        compiled=compiled,
        graph=graph,
        policy_violations=violations,
    )


def format_pipeline_report(report: PipelineGateReport) -> str:
    lines = [
        "DeepScout Pipeline Deterministic Gate",
        f"Fixture: {report.version}",
        f"Status: {'PASS' if report.passed else 'FAIL'}",
    ]
    for stage_name, rows in [
        ("RRF", report.rrf),
        ("Rerank", report.rerank),
        ("Pipeline", report.pipeline),
        ("Contextual contract", report.contextual),
        ("Compiled", report.compiled),
        ("Graph", report.graph),
    ]:
        if not rows:
            continue
        passed = sum(1 for r in rows if r.passed)
        lines.append(f"\n{stage_name}: {passed}/{len(rows)} passed")
        for row in rows:
            if not row.passed:
                lines.append(f"  FAIL {row.case_id}: {', '.join(row.reasons)}")
    if report.policy_violations:
        lines.append("\nPolicy violations:")
        for v in report.policy_violations:
            lines.append(f"  - {v}")
    return "\n".join(lines)
