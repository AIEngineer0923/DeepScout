"""Chunk and embedding persistence — always scoped by research_run_id."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from deepscout_core.domain.enums import IndexingStatus
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from deepscout_persistence.models import ChunkEmbeddingRow, DocumentChunkRow, SourceSnapshotRow


def set_indexing_status(
    session: Session,
    snapshot_id: uuid.UUID,
    status: IndexingStatus,
    *,
    error: str | None = None,
    chunk_count: int | None = None,
    embedding_count: int | None = None,
    chunking_version: str | None = None,
    embedding_spec_key: str | None = None,
) -> None:
    row = session.get(SourceSnapshotRow, snapshot_id)
    if row is None:
        raise LookupError(f"SourceSnapshot {snapshot_id} not found")
    row.indexing_status = status
    row.indexing_error = error
    if chunk_count is not None:
        row.chunk_count = chunk_count
    if embedding_count is not None:
        row.embedding_count = embedding_count
    if chunking_version is not None:
        row.chunking_version = chunking_version
    if embedding_spec_key is not None:
        row.embedding_spec_key = embedding_spec_key
    if status in {IndexingStatus.INDEXED, IndexingStatus.PARTIALLY_INDEXED, IndexingStatus.SKIPPED}:
        row.indexed_at = datetime.now(UTC)
    session.flush()


def existing_chunks(
    session: Session,
    snapshot_id: uuid.UUID,
    *,
    chunking_version: str,
) -> list[DocumentChunkRow]:
    return list(
        session.scalars(
            select(DocumentChunkRow).where(
                DocumentChunkRow.source_snapshot_id == snapshot_id,
                DocumentChunkRow.chunking_version == chunking_version,
            )
        ).all()
    )


def replace_chunks(
    session: Session,
    *,
    run_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    chunking_version: str,
    drafts: list[dict],
) -> list[DocumentChunkRow]:
    existing = existing_chunks(session, snapshot_id, chunking_version=chunking_version)
    if existing:
        return existing
    rows: list[DocumentChunkRow] = []
    for draft in drafts:
        row = DocumentChunkRow(
            research_run_id=run_id,
            source_id=source_id,
            source_snapshot_id=snapshot_id,
            ordinal=draft["ordinal"],
            text=draft["text"],
            context_text=draft.get("context_text"),
            start_offset=draft["start_offset"],
            end_offset=draft["end_offset"],
            token_count=draft["token_count"],
            content_hash=draft["content_hash"],
            section_title=draft.get("section_title"),
            chunking_version=chunking_version,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def existing_embedding_ids(
    session: Session,
    chunk_ids: list[uuid.UUID],
    *,
    provider: str,
    model: str,
    dimensions: int,
    config_version: str,
) -> set[uuid.UUID]:
    if not chunk_ids:
        return set()
    rows = session.scalars(
        select(ChunkEmbeddingRow.chunk_id).where(
            ChunkEmbeddingRow.chunk_id.in_(chunk_ids),
            ChunkEmbeddingRow.provider == provider,
            ChunkEmbeddingRow.model == model,
            ChunkEmbeddingRow.dimensions == dimensions,
            ChunkEmbeddingRow.config_version == config_version,
        )
    )
    return set(rows)


def persist_embeddings(
    session: Session,
    *,
    run_id: uuid.UUID,
    provider: str,
    model: str,
    dimensions: int,
    config_version: str,
    items: list[tuple[uuid.UUID, list[float]]],
) -> int:
    written = 0
    for chunk_id, vector in items:
        if len(vector) != dimensions:
            raise ValueError(f"embedding length {len(vector)} != spec dimensions {dimensions}")
        session.add(
            ChunkEmbeddingRow(
                chunk_id=chunk_id,
                research_run_id=run_id,
                provider=provider,
                model=model,
                dimensions=dimensions,
                config_version=config_version,
                embedding=vector,
            )
        )
        written += 1
    session.flush()
    return written


def dense_search(
    session: Session,
    *,
    run_id: uuid.UUID,
    query_vector: list[float],
    provider: str,
    model: str,
    dimensions: int,
    config_version: str,
    limit: int,
    source_ids: list[uuid.UUID] | None = None,
) -> list[tuple[uuid.UUID, float]]:
    literal = "[" + ",".join(str(float(v)) for v in query_vector) + "]"
    sql = """
        SELECT c.id, (e.embedding <=> CAST(:q AS vector)) AS distance
        FROM chunk_embeddings e
        JOIN document_chunks c ON c.id = e.chunk_id
        WHERE e.research_run_id = :run_id
          AND c.research_run_id = :run_id
          AND e.provider = :provider
          AND e.model = :model
          AND e.dimensions = :dimensions
          AND e.config_version = :config_version
    """
    params: dict = {
        "q": literal,
        "run_id": run_id,
        "provider": provider,
        "model": model,
        "dimensions": dimensions,
        "config_version": config_version,
        "limit": limit,
    }
    if source_ids:
        sql += " AND c.source_id = ANY(:source_ids)"
        params["source_ids"] = source_ids
    sql += " ORDER BY distance ASC LIMIT :limit"
    rows = session.execute(text(sql), params).all()
    return [(row[0], float(row[1])) for row in rows]


def lexical_search(
    session: Session,
    *,
    run_id: uuid.UUID,
    query: str,
    limit: int,
    source_ids: list[uuid.UUID] | None = None,
) -> list[tuple[uuid.UUID, float]]:
    sql = """
        SELECT c.id, ts_rank_cd(c.search_vector, plainto_tsquery('simple', :q)) AS rank
        FROM document_chunks c
        WHERE c.research_run_id = :run_id
          AND c.search_vector @@ plainto_tsquery('simple', :q)
    """
    params: dict = {"q": query, "run_id": run_id, "limit": limit}
    if source_ids:
        sql += " AND c.source_id = ANY(:source_ids)"
        params["source_ids"] = source_ids
    sql += " ORDER BY rank DESC LIMIT :limit"
    rows = session.execute(text(sql), params).all()
    return [(row[0], float(row[1])) for row in rows]


def load_chunks(session: Session, chunk_ids: list[uuid.UUID]) -> dict[uuid.UUID, DocumentChunkRow]:
    if not chunk_ids:
        return {}
    rows = session.scalars(select(DocumentChunkRow).where(DocumentChunkRow.id.in_(chunk_ids))).all()
    return {row.id: row for row in rows}


def list_chunks_for_run(
    session: Session,
    *,
    run_id: uuid.UUID,
    source_ids: list[uuid.UUID] | None = None,
    chunking_version: str | None = None,
) -> list[DocumentChunkRow]:
    stmt = select(DocumentChunkRow).where(DocumentChunkRow.research_run_id == run_id)
    if source_ids:
        stmt = stmt.where(DocumentChunkRow.source_id.in_(source_ids))
    if chunking_version:
        stmt = stmt.where(DocumentChunkRow.chunking_version == chunking_version)
    return list(session.scalars(stmt).all())


def snapshot_run_id(session: Session, snapshot_id: uuid.UUID) -> uuid.UUID | None:
    row = session.execute(
        text(
            """
            SELECT s.research_run_id
            FROM source_snapshots snap
            JOIN sources s ON s.id = snap.source_id
            WHERE snap.id = :snapshot_id
            """
        ),
        {"snapshot_id": snapshot_id},
    ).first()
    return row[0] if row else None
