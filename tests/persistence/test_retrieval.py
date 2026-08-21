"""PostgreSQL retrieval integration — chunks, pgvector, FTS, cross-run isolation."""

from __future__ import annotations

import pytest
from deepscout_core.domain.schemas import ResearchRunCreate, SourceSnapshotWrite, SourceWrite
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_persistence.retrieval import (
    dense_search,
    lexical_search,
    persist_embeddings,
    replace_chunks,
)
from deepscout_research.retrieval.chunking import chunk_snapshot_text
from deepscout_research.retrieval.models import RetrievalQuery
from deepscout_research.retrieval.service import RetrievalService
from deepscout_research.retrieval.spec import (
    CHUNKING_VERSION,
    EMBEDDING_CONFIG_VERSION,
    EmbeddingSpec,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE, EMBEDDING_DIMENSIONS=1536)


def _seed_snapshot(store, settings, *, content: str):
    run = store.create_run(ResearchRunCreate(goal="Retrieval test"), settings)
    source, _ = store.add_source(run.id, SourceWrite(canonical_url="https://example.com/doc", title="Doc"))
    snapshot = store.add_snapshot(source.id, SourceSnapshotWrite(content=content))
    return run, source, snapshot


def _vector(seed: float = 1.0, dims: int = 1536) -> list[float]:
    vec = [0.0] * dims
    vec[0] = seed
    return vec


@pytest.mark.postgres
def test_chunks_lexical_and_dense_search(store, settings, db_session) -> None:
    content = (
        "Solid-state batteries improve energy density. "
        "CVE-2024-9999 affects legacy controllers. "
        "Manufacturers report improved safety margins."
    )
    run, source, snapshot = _seed_snapshot(store, settings, content=content)
    drafts = chunk_snapshot_text(content, snapshot_id=str(snapshot.id))
    rows = replace_chunks(
        db_session,
        run_id=run.id,
        source_id=source.id,
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
            }
            for item in drafts
        ],
    )
    persist_embeddings(
        db_session,
        run_id=run.id,
        provider="google",
        model="gemini-embedding-2",
        dimensions=1536,
        config_version=EMBEDDING_CONFIG_VERSION,
        items=[(row.id, _vector(1.0 + index * 0.01)) for index, row in enumerate(rows)],
    )
    db_session.flush()

    lexical = lexical_search(db_session, run_id=run.id, query="CVE-2024-9999", limit=5)
    assert lexical
    dense = dense_search(
        db_session,
        run_id=run.id,
        query_vector=_vector(1.0),
        provider="google",
        model="gemini-embedding-2",
        dimensions=1536,
        config_version=EMBEDDING_CONFIG_VERSION,
        limit=5,
    )
    assert dense


@pytest.mark.postgres
def test_cross_run_isolation(store, settings, db_session) -> None:
    run_a, source_a, snapshot_a = _seed_snapshot(
        store, settings, content="Alpha run secret phrase about graphene anodes."
    )
    run_b, source_b, snapshot_b = _seed_snapshot(
        store, settings, content="Beta run secret phrase about graphene anodes."
    )
    for run, source, snapshot in ((run_a, source_a, snapshot_a), (run_b, source_b, snapshot_b)):
        drafts = chunk_snapshot_text(snapshot.content_text, snapshot_id=str(snapshot.id))
        rows = replace_chunks(
            db_session,
            run_id=run.id,
            source_id=source.id,
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
                }
                for item in drafts
            ],
        )
        persist_embeddings(
            db_session,
            run_id=run.id,
            provider="google",
            model="gemini-embedding-2",
            dimensions=1536,
            config_version=EMBEDDING_CONFIG_VERSION,
            items=[(row.id, _vector()) for row in rows],
        )
    db_session.flush()

    hits_a = dense_search(
        db_session,
        run_id=run_a.id,
        query_vector=_vector(),
        provider="google",
        model="gemini-embedding-2",
        dimensions=1536,
        config_version=EMBEDDING_CONFIG_VERSION,
        limit=10,
    )
    assert hits_a
    for chunk_id, _ in hits_a:
        row = db_session.get(type(rows[0]), chunk_id)
        assert row.research_run_id == run_a.id


class _FakeEmbeddings:
    def embed_documents(self, texts):
        return [_vector(1.0) for _ in texts]

    def embed_query(self, text):
        return _vector(1.0)


@pytest.mark.postgres
def test_service_does_not_return_other_run_chunks(store, settings, db_session) -> None:
    run_a, source_a, snapshot_a = _seed_snapshot(store, settings, content="Isolation test content here.")
    run_b, _, _ = _seed_snapshot(store, settings, content="Other run.")
    drafts = chunk_snapshot_text(snapshot_a.content_text, snapshot_id=str(snapshot_a.id))
    rows = replace_chunks(
        db_session,
        run_id=run_a.id,
        source_id=source_a.id,
        snapshot_id=snapshot_a.id,
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
            }
            for item in drafts
        ],
    )
    persist_embeddings(
        db_session,
        run_id=run_a.id,
        provider="google",
        model="gemini-embedding-2",
        dimensions=1536,
        config_version=EMBEDDING_CONFIG_VERSION,
        items=[(row.id, _vector()) for row in rows],
    )
    db_session.flush()
    service = RetrievalService(
        store,
        settings,
        client=_FakeEmbeddings(),
        spec=EmbeddingSpec(
            provider="google",
            model="gemini-embedding-2",
            dimensions=1536,
        ),
    )
    hits = service.retrieve(
        RetrievalQuery(
            query="Isolation test",
            run_id=run_b.id,
            mode="hybrid",
        )
    )
    assert hits == []
