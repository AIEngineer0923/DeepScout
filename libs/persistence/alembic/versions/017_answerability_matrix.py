"""017 generic answerability matrix and research funnel.

Revision ID: 017
Revises: 016
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entity_research_matrices",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="3"),
        sa.Column(
            "matrix",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_entity_research_matrices_run_id", "entity_research_matrices", ["research_run_id"]
    )
    op.create_table(
        "research_funnels",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "rejection_counts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "rejection_samples",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_research_funnels_run_id", "research_funnels", ["research_run_id"])


def downgrade() -> None:
    op.drop_index("ix_research_funnels_run_id", table_name="research_funnels")
    op.drop_table("research_funnels")
    op.drop_index("ix_entity_research_matrices_run_id", table_name="entity_research_matrices")
    op.drop_table("entity_research_matrices")
