"""Phase 5 retrieval tables: chunks, embeddings, snapshot indexing status, FTS.

Revision ID: 005
Revises: 004
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    indexing_status = postgresql.ENUM(
        "pending",
        "indexing",
        "indexed",
        "partially_indexed",
        "failed",
        "skipped",
        name="indexing_status",
    )
    indexing_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "source_snapshots",
        sa.Column(
            "indexing_status",
            indexing_status,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("source_snapshots", sa.Column("indexing_error", sa.Text(), nullable=True))
    op.add_column(
        "source_snapshots",
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "source_snapshots",
        sa.Column("embedding_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "source_snapshots", sa.Column("chunking_version", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "source_snapshots",
        sa.Column("embedding_spec_key", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "source_snapshots", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_snapshot_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("source_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("section_title", sa.String(length=200), nullable=True),
        sa.Column("chunking_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "source_snapshot_id",
            "chunking_version",
            "ordinal",
            name="uq_chunks_snapshot_version_ord",
        ),
    )
    op.create_index("ix_document_chunks_run_id", "document_chunks", ["research_run_id"])
    op.create_index("ix_document_chunks_snapshot_id", "document_chunks", ["source_snapshot_id"])
    op.execute(
        "ALTER TABLE document_chunks ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text, ''))) STORED"
    )
    op.execute("CREATE INDEX ix_document_chunks_fts ON document_chunks USING GIN (search_vector)")

    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "chunk_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("config_version", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "chunk_id",
            "provider",
            "model",
            "dimensions",
            "config_version",
            name="uq_chunk_embedding_space",
        ),
    )
    op.create_index("ix_chunk_embeddings_run_id", "chunk_embeddings", ["research_run_id"])


def downgrade() -> None:
    op.drop_index("ix_chunk_embeddings_run_id", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_fts")
    op.drop_index("ix_document_chunks_snapshot_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_run_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_column("source_snapshots", "indexed_at")
    op.drop_column("source_snapshots", "embedding_spec_key")
    op.drop_column("source_snapshots", "chunking_version")
    op.drop_column("source_snapshots", "embedding_count")
    op.drop_column("source_snapshots", "chunk_count")
    op.drop_column("source_snapshots", "indexing_error")
    op.drop_column("source_snapshots", "indexing_status")
    postgresql.ENUM(name="indexing_status").drop(op.get_bind(), checkfirst=True)
