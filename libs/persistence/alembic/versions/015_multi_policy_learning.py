"""015 multi-policy learning expansion.

Revision ID: 015
Revises: 014
Create Date: 2026-08-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_policy_versions",
        sa.Column("policy_family", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "learning_policy_versions",
        sa.Column("scope_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "learning_policy_versions",
        sa.Column(
            "parent_version_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("learning_policy_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "learning_policy_versions",
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "learning_policy_versions",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_learning_policy_versions_family",
        "learning_policy_versions",
        ["policy_family"],
    )

    op.create_table(
        "learning_audit_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("policy_key", sa.String(length=128)),
        sa.Column("policy_family", sa.String(length=64)),
        sa.Column("owner_principal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("principals.id", ondelete="CASCADE")),
        sa.Column("learning_case_id", sa.Uuid(as_uuid=True), sa.ForeignKey("learning_cases.id", ondelete="SET NULL")),
        sa.Column(
            "candidate_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("improvement_candidates.id", ondelete="SET NULL"),
        ),
        sa.Column("policy_version_id", sa.Uuid(as_uuid=True)),
        sa.Column("actor_principal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("principals.id", ondelete="SET NULL")),
        sa.Column("actor_label", sa.String(length=128), nullable=False, server_default="system"),
        sa.Column("previous_version_label", sa.String(length=64)),
        sa.Column("new_version_label", sa.String(length=64)),
        sa.Column("reason", sa.Text()),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_learning_audit_events_type", "learning_audit_events", ["event_type"])
    op.create_index("ix_learning_audit_events_owner", "learning_audit_events", ["owner_principal_id"])
    op.create_index("ix_learning_audit_events_created", "learning_audit_events", ["created_at"])

    op.execute(
        "UPDATE learning_policy_versions SET policy_family = 'corrective_research', "
        "scope_key = 'global' WHERE policy_key = 'global.corrective_research'"
    )


def downgrade() -> None:
    op.drop_index("ix_learning_audit_events_created", table_name="learning_audit_events")
    op.drop_index("ix_learning_audit_events_owner", table_name="learning_audit_events")
    op.drop_index("ix_learning_audit_events_type", table_name="learning_audit_events")
    op.drop_table("learning_audit_events")
    op.drop_index("ix_learning_policy_versions_family", table_name="learning_policy_versions")
    op.drop_column("learning_policy_versions", "superseded_at")
    op.drop_column("learning_policy_versions", "activated_at")
    op.drop_column("learning_policy_versions", "parent_version_id")
    op.drop_column("learning_policy_versions", "scope_key")
    op.drop_column("learning_policy_versions", "policy_family")
