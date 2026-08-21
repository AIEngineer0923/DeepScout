"""PostgreSQL compiled knowledge — provenance, rebuild, isolation."""

from __future__ import annotations

import pytest
from deepscout_core.domain.enums import WikiLinkType, WikiPageType
from deepscout_core.domain.schemas import (
    ClaimWrite,
    EvidenceWrite,
    ResearchRunCreate,
    SourceSnapshotWrite,
    SourceWrite,
)
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_persistence import knowledge as knowledge_store
from deepscout_research.knowledge.obsidian_export import export_run_wiki_markdown
from deepscout_research.phases.compile_knowledge import compile_knowledge_for_run


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE)


@pytest.mark.postgres
def test_rebuild_wiki_requires_evidence_and_is_idempotent(store, settings, db_session) -> None:
    run = store.create_run(ResearchRunCreate(goal="wiki compile"), settings)
    source, _ = store.add_source(run.id, SourceWrite(canonical_url="https://ex.test/a", title="A"))
    snapshot = store.add_snapshot(source.id, SourceSnapshotWrite(content="Solid-state batteries improve safety margins significantly."))
    claim = store.add_claim(run.id, ClaimWrite(statement="Solid-state batteries improve safety margins significantly.", source_id=source.id))
    store.attach_evidence(
        claim.id,
        EvidenceWrite(
            snapshot_id=snapshot.id,
            quote="Solid-state batteries improve safety margins significantly.",
            locator="offset:0-56",
            support_strength=1.0,
            confidence=1.0,
        ),
    )
    bare = store.add_claim(run.id, ClaimWrite(statement="No evidence claim should be skipped."))
    store.commit()

    first = compile_knowledge_for_run(store, run.id)
    store.commit()
    second = compile_knowledge_for_run(store, run.id)
    store.commit()

    statements = knowledge_store.list_statements_for_run(db_session, run.id)
    assert first["statements_created"] == 1
    assert second["statements_created"] == 0
    assert second["statements_confirmed"] >= 1
    assert first["claims_skipped_no_evidence"] >= 1
    assert len(statements) == 1
    assert statements[0].claim_id == claim.id
    assert statements[0].evidence_id is not None
    assert bare.id not in {s.claim_id for s in statements}

    files = export_run_wiki_markdown(store, run.id)
    assert any(path.endswith("run-findings.md") for path in files)
    assert "Solid-state batteries" in "\n".join(files.values())


@pytest.mark.postgres
def test_cross_run_statement_rejected(store, settings, db_session) -> None:
    run_a = store.create_run(ResearchRunCreate(goal="run a"), settings)
    run_b = store.create_run(ResearchRunCreate(goal="run b"), settings)
    source, _ = store.add_source(run_a.id, SourceWrite(canonical_url="https://ex.test/b", title="B"))
    snapshot = store.add_snapshot(source.id, SourceSnapshotWrite(content="Enough text for a quote about energy density improvements."))
    claim = store.add_claim(run_a.id, ClaimWrite(statement="Enough text for a quote about energy density improvements.", source_id=source.id))
    evidence = store.attach_evidence(
        claim.id,
        EvidenceWrite(
            snapshot_id=snapshot.id,
            quote="Enough text for a quote about energy density improvements.",
            locator="offset:0-58",
            support_strength=1.0,
            confidence=1.0,
        ),
    )
    page = knowledge_store.create_page(
        db_session,
        run_id=run_b.id,
        slug="foreign",
        title="Foreign",
        page_type=WikiPageType.TOPIC,
    )
    store.commit()
    with pytest.raises(PermissionError):
        knowledge_store.add_statement(
            db_session,
            run_id=run_b.id,
            page_id=page.id,
            statement_text=claim.statement,
            claim_id=claim.id,
            evidence_id=evidence.id,
        )


@pytest.mark.postgres
def test_lint_bounds_cycles(store, settings, db_session) -> None:
    run = store.create_run(ResearchRunCreate(goal="cycles"), settings)
    a = knowledge_store.create_page(
        db_session, run_id=run.id, slug="a", title="A", page_type=WikiPageType.TOPIC
    )
    b = knowledge_store.create_page(
        db_session, run_id=run.id, slug="b", title="B", page_type=WikiPageType.TOPIC
    )
    knowledge_store.add_link(
        db_session, run_id=run.id, from_page_id=a.id, to_page_id=b.id, link_type=WikiLinkType.RELATED_TO
    )
    knowledge_store.add_link(
        db_session, run_id=run.id, from_page_id=b.id, to_page_id=a.id, link_type=WikiLinkType.RELATED_TO
    )
    store.commit()
    lint = knowledge_store.lint_wiki(db_session, run.id, max_hops=8)
    assert lint["page_count"] == 2
    assert lint["cyclic_nodes_bounded"]
