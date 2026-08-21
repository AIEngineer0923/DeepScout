"""Follow-up lineage, source preferences, monitors, RUM, task semantics.

Revision ID: 010
Revises: 009
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_runs",
        sa.Column("root_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "research_runs",
        sa.Column("monitor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "research_runs",
        sa.Column("lineage_kind", sa.String(length=16), nullable=False, server_default="none"),
    )
    op.create_index("ix_research_runs_parent_run_id", "research_runs", ["parent_run_id"])
    op.create_index("ix_research_runs_root_run_id", "research_runs", ["root_run_id"])
    op.create_index("ix_research_runs_monitor_id", "research_runs", ["monitor_id"])
    op.create_foreign_key(
        "fk_research_runs_root",
        "research_runs",
        "research_runs",
        ["root_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("research_tasks", sa.Column("task_meta", postgresql.JSONB(), nullable=True))

    op.create_table(
        "research_source_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("research_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("identity_kind", sa.String(length=16), nullable=False),
        sa.Column("identity_value", sa.String(length=2048), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("origin", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "research_run_id",
            "action",
            "identity_kind",
            "identity_value",
            name="uq_source_pref_run_identity",
        ),
    )
    op.create_index(
        "ix_source_preferences_run_id",
        "research_source_preferences",
        ["research_run_id"],
    )

    op.create_table(
        "research_monitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("schedule_kind", sa.String(length=16), nullable=False, server_default="daily"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("hour", sa.Integer(), nullable=False, server_default="9"),
        sa.Column("minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weekday", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("research_mode", sa.String(length=16), nullable=False, server_default="standard"),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_change_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["research_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_run_id"], ["research_runs.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_research_monitors_next_run_at", "research_monitors", ["next_run_at"])
    op.create_index("ix_research_monitors_enabled", "research_monitors", ["enabled"])
    op.create_foreign_key(
        "fk_research_runs_monitor",
        "research_runs",
        "research_monitors",
        ["monitor_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "web_vital_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("route", sa.String(length=128), nullable=False),
        sa.Column("lcp_ms", sa.Float(), nullable=True),
        sa.Column("inp_ms", sa.Float(), nullable=True),
        sa.Column("cls", sa.Float(), nullable=True),
        sa.Column("ttfb_ms", sa.Float(), nullable=True),
        sa.Column("fcp_ms", sa.Float(), nullable=True),
        sa.Column("navigation_type", sa.String(length=32), nullable=False, server_default="navigate"),
        sa.Column("device_class", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("network_class", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="field"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_web_vital_samples_created_at", "web_vital_samples", ["created_at"])
    op.create_index("ix_web_vital_samples_route", "web_vital_samples", ["route"])


def downgrade() -> None:
    op.drop_index("ix_web_vital_samples_route", table_name="web_vital_samples")
    op.drop_index("ix_web_vital_samples_created_at", table_name="web_vital_samples")
    op.drop_table("web_vital_samples")
    op.drop_constraint("fk_research_runs_monitor", "research_runs", type_="foreignkey")
    op.drop_index("ix_research_monitors_enabled", table_name="research_monitors")
    op.drop_index("ix_research_monitors_next_run_at", table_name="research_monitors")
    op.drop_table("research_monitors")
    op.drop_index("ix_source_preferences_run_id", table_name="research_source_preferences")
    op.drop_table("research_source_preferences")
    op.drop_column("research_tasks", "task_meta")
    op.drop_constraint("fk_research_runs_root", "research_runs", type_="foreignkey")
    op.drop_index("ix_research_runs_monitor_id", table_name="research_runs")
    op.drop_index("ix_research_runs_root_run_id", table_name="research_runs")
    op.drop_index("ix_research_runs_parent_run_id", table_name="research_runs")
    op.drop_column("research_runs", "lineage_kind")
    op.drop_column("research_runs", "monitor_id")
    op.drop_column("research_runs", "root_run_id")
