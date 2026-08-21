"""Phase 6 compiled knowledge: run-scoped wiki pages, statements, links, relations.

Revision ID: 006
Revises: 005
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    enums = {
        "wiki_page_type": ("topic", "entity", "concept", "finding", "contradiction", "question"),
        "wiki_page_status": ("active", "stale", "superseded"),
        "wiki_change_op": (
            "create",
            "confirm",
            "refine",
            "contradict",
            "supersede",
            "mark_stale",
            "no_change",
        ),
        "wiki_statement_status": ("active", "stale", "superseded", "contradicted"),
        "wiki_link_type": ("related_to", "contradicts", "derived_from", "mentions"),
        "knowledge_relation_type": (
            "supports",
            "refutes",
            "contradicts",
            "confirms",
            "supersedes",
            "related_to",
        ),
        "knowledge_provenance_kind": ("deterministic", "llm_inferred"),
    }
    created: dict[str, postgresql.ENUM] = {}
    for name, values in enums.items():
        enum = postgresql.ENUM(*values, name=name, create_type=False)
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
        created[name] = enum

    wiki_page_type = created["wiki_page_type"]
    wiki_page_status = created["wiki_page_status"]
    wiki_change_op = created["wiki_change_op"]
    wiki_statement_status = created["wiki_statement_status"]
    wiki_link_type = created["wiki_link_type"]
    knowledge_relation_type = created["knowledge_relation_type"]
    knowledge_provenance_kind = created["knowledge_provenance_kind"]

    op.create_table(
        "wiki_pages",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("page_type", wiki_page_type, nullable=False),
        sa.Column("status", wiki_page_status, nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("body_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("research_run_id", "slug", name="uq_wiki_pages_run_slug"),
    )
    op.create_index("ix_wiki_pages_run_id", "wiki_pages", ["research_run_id"])

    op.create_table(
        "wiki_revisions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "page_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("change_op", wiki_change_op, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("page_id", "revision", name="uq_wiki_revisions_page_rev"),
    )

    op.create_table(
        "wiki_statements",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "page_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("statement_text", sa.Text(), nullable=False),
        sa.Column("status", wiki_statement_status, nullable=False, server_default="active"),
        sa.Column(
            "claim_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "evidence_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "compiled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_wiki_statements_run_id", "wiki_statements", ["research_run_id"])
    op.create_index("ix_wiki_statements_claim_id", "wiki_statements", ["claim_id"])

    op.create_table(
        "wiki_links",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_page_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_page_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("link_type", wiki_link_type, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("from_page_id", "to_page_id", "link_type", name="uq_wiki_links_edge"),
    )
    op.create_index("ix_wiki_links_run_id", "wiki_links", ["research_run_id"])

    op.create_table(
        "knowledge_relations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_statement_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("wiki_statements.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "to_statement_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("wiki_statements.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("relation_type", knowledge_relation_type, nullable=False),
        sa.Column("provenance_kind", knowledge_provenance_kind, nullable=False),
        sa.Column(
            "claim_a_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "claim_b_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_knowledge_relations_run_id", "knowledge_relations", ["research_run_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_relations_run_id", table_name="knowledge_relations")
    op.drop_table("knowledge_relations")
    op.drop_index("ix_wiki_links_run_id", table_name="wiki_links")
    op.drop_table("wiki_links")
    op.drop_index("ix_wiki_statements_claim_id", table_name="wiki_statements")
    op.drop_index("ix_wiki_statements_run_id", table_name="wiki_statements")
    op.drop_table("wiki_statements")
    op.drop_table("wiki_revisions")
    op.drop_index("ix_wiki_pages_run_id", table_name="wiki_pages")
    op.drop_table("wiki_pages")
    bind = op.get_bind()
    for name in (
        "knowledge_provenance_kind",
        "knowledge_relation_type",
        "wiki_link_type",
        "wiki_statement_status",
        "wiki_change_op",
        "wiki_page_status",
        "wiki_page_type",
    ):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
