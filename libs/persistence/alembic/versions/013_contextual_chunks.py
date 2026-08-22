"""Contextual chunks + retrieval trace metadata.

Revision ID: 013
Revises: 012
Create Date: 2026-08-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("context_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "context_text")
