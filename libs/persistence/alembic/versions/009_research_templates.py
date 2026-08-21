"""Research templates — local saved presets (MODE A).

Revision ID: 009
Revises: 008
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("research_mode", sa.String(length=16), nullable=False, server_default="standard"),
        sa.Column("output_language", sa.String(length=16), nullable=False, server_default="en"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_research_templates_updated_at", "research_templates", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_research_templates_updated_at", table_name="research_templates")
    op.drop_table("research_templates")
