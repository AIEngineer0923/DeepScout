"""016 learning experience, monitoring, and experiment jobs.

Revision ID: 016
Revises: 015
Create Date: 2026-08-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_experience_samples",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_principal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("principals.id", ondelete="CASCADE")),
        sa.Column("strategy_key", sa.String(length=64), nullable=False),
        sa.Column("quality", sa.Float(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False),
        sa.Column("research_run_id", sa.Uuid(as_uuid=True), sa.ForeignKey("research_runs.id", ondelete="CASCADE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_learning_experience_owner_strategy",
        "learning_experience_samples",
        ["owner_principal_id", "strategy_key"],
    )

    op.create_table(
        "learning_policy_monitoring",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "policy_version_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("learning_policy_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("policy_key", sa.String(length=128), nullable=False),
        sa.Column("policy_family", sa.String(length=64), nullable=False),
        sa.Column("owner_principal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("principals.id", ondelete="CASCADE")),
        sa.Column("window_start", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("observed_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("observed_samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_learning_policy_monitoring_key", "learning_policy_monitoring", ["policy_key", "status"])

    op.create_table(
        "learning_experiment_jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("improvement_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_principal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("principals.id", ondelete="CASCADE")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("cost_category", sa.String(length=32), nullable=False, server_default="learning_experiment"),
        sa.Column("lease_owner", sa.String(length=128)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_learning_experiment_jobs_status", "learning_experiment_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_learning_experiment_jobs_status", table_name="learning_experiment_jobs")
    op.drop_table("learning_experiment_jobs")
    op.drop_index("ix_learning_policy_monitoring_key", table_name="learning_policy_monitoring")
    op.drop_table("learning_policy_monitoring")
    op.drop_index("ix_learning_experience_owner_strategy", table_name="learning_experience_samples")
    op.drop_table("learning_experience_samples")
