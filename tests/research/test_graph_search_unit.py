"""Graph search unit tests — local 1-hop knowledge_relations traversal."""

from __future__ import annotations

import pytest
from deepscout_core.domain.enums import KnowledgeProvenanceKind, KnowledgeRelationType, WikiPageType
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_persistence import knowledge as knowledge_store
from deepscout_research.retrieval.graph_search import graph_search_statements


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE)


@pytest.mark.postgres
def test_graph_search_entity_match_and_one_hop(store, settings, db_session) -> None:
    run = store.create_run(ResearchRunCreate(goal="graph unit"), settings)
    page = knowledge_store.create_page(
        db_session,
        run_id=run.id,
        slug="supply",
        title="Supply",
        page_type=WikiPageType.TOPIC,
    )
    alpha = knowledge_store.add_statement(
        db_session,
        run_id=run.id,
        page_id=page.id,
        statement_text="AlphaCells manufactures SS-CELL-900X cells.",
        claim_id=None,
        evidence_id=None,
    )
    beta = knowledge_store.add_statement(
        db_session,
        run_id=run.id,
        page_id=page.id,
        statement_text="FleetOperator Beta operates pilot fleets in the EU.",
        claim_id=None,
        evidence_id=None,
    )
    advisory = knowledge_store.add_statement(
        db_session,
        run_id=run.id,
        page_id=page.id,
        statement_text="ADV-BMS-2024-09 references CVE-2024-1234.",
        claim_id=None,
        evidence_id=None,
    )
    knowledge_store.add_relation(
        db_session,
        run_id=run.id,
        from_statement_id=alpha.id,
        to_statement_id=beta.id,
        relation_type=KnowledgeRelationType.RELATED_TO,
        provenance_kind=KnowledgeProvenanceKind.DETERMINISTIC,
    )
    knowledge_store.add_relation(
        db_session,
        run_id=run.id,
        from_statement_id=beta.id,
        to_statement_id=advisory.id,
        relation_type=KnowledgeRelationType.RELATED_TO,
        provenance_kind=KnowledgeProvenanceKind.DETERMINISTIC,
    )
    store.commit()

    hits = graph_search_statements(
        db_session, run_id=run.id, query="AlphaCells FleetOperator", limit=5
    )
    reasons = {reason for _, reason in hits}
    assert "entity_match" in reasons
    assert any("graph_hop" in reason for reason in reasons)


@pytest.mark.postgres
def test_graph_search_run_isolation(store, settings, db_session) -> None:
    run_a = store.create_run(ResearchRunCreate(goal="graph a"), settings)
    run_b = store.create_run(ResearchRunCreate(goal="graph b"), settings)
    page = knowledge_store.create_page(
        db_session,
        run_id=run_a.id,
        slug="only-a",
        title="Only A",
        page_type=WikiPageType.TOPIC,
    )
    knowledge_store.add_statement(
        db_session,
        run_id=run_a.id,
        page_id=page.id,
        statement_text="AlphaCells secret relation data.",
        claim_id=None,
        evidence_id=None,
    )
    store.commit()
    hits = graph_search_statements(db_session, run_id=run_b.id, query="AlphaCells", limit=5)
    assert hits == []


@pytest.mark.postgres
def test_graph_search_no_false_positive(store, settings, db_session) -> None:
    run = store.create_run(ResearchRunCreate(goal="graph empty"), settings)
    store.commit()
    hits = graph_search_statements(
        db_session, run_id=run.id, query="quantum computing CBAM", limit=5
    )
    assert hits == []
