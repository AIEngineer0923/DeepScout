"""014 learning experience tables.

Revision ID: 014
Revises: 013
Create Date: 2026-08-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_cases",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("case_key", sa.String(length=128), nullable=False),
        sa.Column("owner_principal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("principals.id", ondelete="CASCADE")),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("subsystem", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=64), nullable=False),
        sa.Column("symptom", sa.Text(), nullable=False),
        sa.Column("expected_behavior", sa.Text(), nullable=False, server_default=""),
        sa.Column("observed_behavior", sa.Text(), nullable=False, server_default=""),
        sa.Column("origin", sa.String(length=64), nullable=False),
        sa.Column("trust_level", sa.String(length=64), nullable=False),
        sa.Column("review_state", sa.String(length=64), nullable=False),
        sa.Column("sanitized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("human_reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("root_cause_class", sa.String(length=64)),
        sa.Column("is_root_cause", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("downstream_symptom_of", sa.String(length=128)),
        sa.Column("diagnostic_evidence", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("evaluator_signals", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("affected_requirements", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("reproducibility", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("architecture_version", sa.String(length=32), nullable=False, server_default="learning-v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("case_key", "owner_principal_id", name="uq_learning_cases_key_owner"),
    )
    op.create_index("ix_learning_cases_owner", "learning_cases", ["owner_principal_id"])
    op.create_index("ix_learning_cases_review_state", "learning_cases", ["review_state"])

    op.create_table(
        "improvement_candidates",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("candidate_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column(
            "learning_case_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("learning_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_principal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("principals.id", ondelete="CASCADE")),
        sa.Column("candidate_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("policy_delta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_benefit", sa.Text(), nullable=False, server_default=""),
        sa.Column("possible_regressions", sa.Text(), nullable=False, server_default=""),
        sa.Column("affected_subsystem", sa.String(length=32), nullable=False),
        sa.Column("evaluation_plan", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("supporting_case_ids", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("trust_level", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("rollback_info", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("experiment_result", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("promotion_verdict", sa.String(length=64)),
        sa.Column("promotion_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_improvement_candidates_case", "improvement_candidates", ["learning_case_id"])
    op.create_index("ix_improvement_candidates_owner", "improvement_candidates", ["owner_principal_id"])
    op.create_index("ix_improvement_candidates_status", "improvement_candidates", ["status"])

    op.create_table(
        "learning_policy_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("policy_key", sa.String(length=128), nullable=False),
        sa.Column("version_label", sa.String(length=64), nullable=False),
        sa.Column("owner_principal_id", sa.Uuid(as_uuid=True), sa.ForeignKey("principals.id", ondelete="CASCADE")),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("promoted_from_candidate_id", sa.Uuid(as_uuid=True)),
        sa.Column("promotion_reason", sa.Text()),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("superseded_by", sa.Uuid(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_learning_policy_versions_key", "learning_policy_versions", ["policy_key"])
    op.create_index("ix_learning_policy_versions_active", "learning_policy_versions", ["active"])
    op.create_index("ix_learning_policy_versions_owner", "learning_policy_versions", ["owner_principal_id"])


def downgrade() -> None:
    op.drop_index("ix_learning_policy_versions_owner", table_name="learning_policy_versions")
    op.drop_index("ix_learning_policy_versions_active", table_name="learning_policy_versions")
    op.drop_index("ix_learning_policy_versions_key", table_name="learning_policy_versions")
    op.drop_table("learning_policy_versions")
    op.drop_index("ix_improvement_candidates_status", table_name="improvement_candidates")
    op.drop_index("ix_improvement_candidates_owner", table_name="improvement_candidates")
    op.drop_index("ix_improvement_candidates_case", table_name="improvement_candidates")
    op.drop_table("improvement_candidates")
    op.drop_index("ix_learning_cases_review_state", table_name="learning_cases")
    op.drop_index("ix_learning_cases_owner", table_name="learning_cases")
    op.drop_table("learning_cases")
