"""Phase 3: search candidates and contradiction evidence status.

Revision ID: 002
Revises: 001
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    contradiction_evidence_status = postgresql.ENUM(
        "sufficient",
        "insufficient_evidence",
        name="contradiction_evidence_status",
        create_type=False,
    )
    bind = op.get_bind()
    contradiction_evidence_status.create(bind, checkfirst=True)

    op.add_column(
        "contradictions",
        sa.Column(
            "evidence_status",
            contradiction_evidence_status,
            nullable=False,
            server_default="sufficient",
        ),
    )

    op.create_table(
        "search_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_run_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=True),
        sa.Column("query", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["question_id"], ["research_questions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "research_run_id",
            "query",
            "url",
            name="uq_search_candidates_run_query_url",
        ),
    )
    op.create_index("ix_search_candidates_run_id", "search_candidates", ["research_run_id"])


def downgrade() -> None:
    op.drop_index("ix_search_candidates_run_id", table_name="search_candidates")
    op.drop_table("search_candidates")
    op.drop_column("contradictions", "evidence_status")
    postgresql.ENUM(name="contradiction_evidence_status").drop(op.get_bind(), checkfirst=True)
