"""Persist research mode and report output language.

Revision ID: 004
Revises: 003
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_runs",
        sa.Column("research_mode", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "research_runs",
        sa.Column(
            "output_language",
            sa.String(length=16),
            nullable=False,
            server_default="en",
        ),
    )


def downgrade() -> None:
    op.drop_column("research_runs", "output_language")
    op.drop_column("research_runs", "research_mode")
