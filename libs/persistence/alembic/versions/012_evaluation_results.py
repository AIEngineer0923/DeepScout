"""Persisted evaluation results per research run.

Revision ID: 012
Revises: 011
Create Date: 2026-08-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evaluator_id", sa.String(length=128), nullable=False),
        sa.Column("evaluator_version", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=64), nullable=False),
        sa.Column("applicability", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "research_run_id",
            "evaluator_id",
            name="uq_evaluation_results_run_evaluator",
        ),
    )
    op.create_index("ix_evaluation_results_run_id", "evaluation_results", ["research_run_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_results_run_id", table_name="evaluation_results")
    op.drop_table("evaluation_results")
