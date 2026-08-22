"""Compiled knowledge retrieval — run-scoped statements, not evidence authority."""

from __future__ import annotations

import pytest
from deepscout_core.domain.schemas import (
    ClaimWrite,
    EvidenceWrite,
    ResearchRunCreate,
    SourceSnapshotWrite,
    SourceWrite,
)
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_evaluation.retrieval_quality import evaluate_compiled_retrieval, load_benchmark_v2
from deepscout_research.phases.compile_knowledge import compile_knowledge_for_run
from deepscout_research.retrieval.models import RetrievalQuery
from deepscout_research.retrieval.service import RetrievalService


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE, RETRIEVAL_ROUTER_ENABLED=True)


@pytest.mark.postgres
def test_compiled_retrieval_returns_wiki_statements(store, settings, db_session) -> None:
    benchmark = load_benchmark_v2()
    fixture = benchmark["compiled_fixture"]
    run = store.create_run(ResearchRunCreate(goal="compiled retrieval"), settings)
    doc = benchmark["documents"][0]
    source, _ = store.add_source(
        run.id,
        SourceWrite(canonical_url="https://benchmark.local/doc-battery", title=doc["title"]),
    )
    snapshot = store.add_snapshot(source.id, SourceSnapshotWrite(content=doc["text"]))
    claim_spec = fixture["claims"][0]
    claim = store.add_claim(
        run.id,
        ClaimWrite(statement=claim_spec["statement"], source_id=source.id),
    )
    store.attach_evidence(
        claim.id,
        EvidenceWrite(
            snapshot_id=snapshot.id,
            quote=claim_spec["quote"],
            locator="offset:0-80",
            support_strength=1.0,
            confidence=1.0,
        ),
    )
    store.commit()
    compile_knowledge_for_run(store, run.id)
    store.commit()

    service = RetrievalService(store, settings)
    hits = service.retrieve(
        RetrievalQuery(
            query="what have we learned about energy density",
            run_id=run.id,
            top_k=5,
            candidate_k=15,
            corpus="compiled",
        )
    )
    compiled = [h for h in hits if h.provenance_kind == "compiled"]
    assert compiled, "expected compiled wiki statement in results"
    assert all(h.retrieval_reason == "compiled_knowledge" for h in compiled)


@pytest.mark.postgres
def test_compiled_benchmark_fixture_passes(store, settings, db_session) -> None:
    benchmark = load_benchmark_v2()
    fixture = benchmark["compiled_fixture"]
    run = store.create_run(ResearchRunCreate(goal="compiled bench"), settings)
    for claim_spec in fixture["claims"]:
        doc = next(d for d in benchmark["documents"] if d["id"] == claim_spec["doc_id"])
        source, _ = store.add_source(
            run.id,
            SourceWrite(canonical_url=f"https://bench.local/{doc['id']}", title=doc["title"]),
        )
        snapshot = store.add_snapshot(source.id, SourceSnapshotWrite(content=doc["text"]))
        claim = store.add_claim(
            run.id,
            ClaimWrite(statement=claim_spec["statement"], source_id=source.id),
        )
        store.attach_evidence(
            claim.id,
            EvidenceWrite(
                snapshot_id=snapshot.id,
                quote=claim_spec["quote"],
                locator="offset:0-80",
                support_strength=1.0,
                confidence=1.0,
            ),
        )
    store.commit()
    compile_knowledge_for_run(store, run.id)
    store.commit()
    service = RetrievalService(store, settings)
    result = evaluate_compiled_retrieval(service, run_id=run.id, fixture=fixture)
    assert result["passed"] == len(fixture["queries"])
