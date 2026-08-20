"""Phase 4: durable jobs, task DAG, usage accounting, run events.

Revision ID: 003
Revises: 002
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    research_task_status = postgresql.ENUM(
        "pending",
        "ready",
        "running",
        "completed",
        "failed",
        "cancelled",
        "blocked",
        name="research_task_status",
        create_type=False,
    )
    research_job_type = postgresql.ENUM(
        "execute_run",
        "resume_run",
        name="research_job_type",
        create_type=False,
    )
    research_job_status = postgresql.ENUM(
        "pending",
        "claimed",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="research_job_status",
        create_type=False,
    )
    usage_report_status = postgresql.ENUM(
        "unknown",
        "partial",
        "complete",
        name="usage_report_status",
        create_type=False,
    )
    cost_report_status = postgresql.ENUM(
        "unknown",
        "estimated",
        "known",
        name="cost_report_status",
        create_type=False,
    )

    for enum in (
        research_task_status,
        research_job_type,
        research_job_status,
        usage_report_status,
        cost_report_status,
    ):
        enum.create(bind, checkfirst=True)

    op.add_column("research_runs", sa.Column("termination_reason", sa.String(length=64)))
    op.add_column(
        "research_runs",
        sa.Column("concurrency_limit", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "research_runs",
        sa.Column(
            "usage_report_status", usage_report_status, nullable=False, server_default="unknown"
        ),
    )
    op.add_column(
        "research_runs",
        sa.Column(
            "cost_report_status", cost_report_status, nullable=False, server_default="unknown"
        ),
    )
    op.add_column("research_runs", sa.Column("pricing_version", sa.String(length=32)))
    op.alter_column("research_runs", "consumed_total_tokens", nullable=True)

    op.create_table(
        "research_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_run_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=True),
        sa.Column("task_key", sa.String(length=64), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", research_task_status, nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "depends_on",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "allowed_tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='["web_search"]',
        ),
        sa.Column("model_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("delegated_budget", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("worker_id", sa.Uuid(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("error_message", sa.Text()),
        sa.Column("checkpoint", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["question_id"], ["research_questions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("research_run_id", "task_key", name="uq_research_tasks_run_key"),
    )
    op.create_index("ix_research_tasks_run_id", "research_tasks", ["research_run_id"])
    op.create_index("ix_research_tasks_status", "research_tasks", ["status"])

    op.create_table(
        "research_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_run_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", research_job_type, nullable=False),
        sa.Column("status", research_job_status, nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column("lease_owner", sa.String(length=128)),
        sa.Column("lease_token", sa.String(length=64)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_research_jobs_idempotency"),
    )
    op.create_index("ix_research_jobs_status", "research_jobs", ["status"])
    op.create_index("ix_research_jobs_run_id", "research_jobs", ["research_run_id"])

    op.create_table(
        "run_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("research_run_id", "sequence", name="uq_run_events_run_sequence"),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["research_run_id"])

    op.create_table(
        "token_usage_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_run_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("agent_role", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("worker_id", sa.Uuid(), nullable=True),
        sa.Column("iteration", sa.Integer()),
        sa.Column("retry", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("cached_input_tokens", sa.Integer()),
        sa.Column("reasoning_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("cost_usd", sa.Float()),
        sa.Column(
            "usage_report_status", usage_report_status, nullable=False, server_default="unknown"
        ),
        sa.Column(
            "cost_report_status", cost_report_status, nullable=False, server_default="unknown"
        ),
        sa.Column("pricing_version", sa.String(length=32)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["research_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_token_usage_records_run_id", "token_usage_records", ["research_run_id"])


def downgrade() -> None:
    op.drop_index("ix_token_usage_records_run_id", table_name="token_usage_records")
    op.drop_table("token_usage_records")
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ix_research_jobs_run_id", table_name="research_jobs")
    op.drop_index("ix_research_jobs_status", table_name="research_jobs")
    op.drop_table("research_jobs")
    op.drop_index("ix_research_tasks_status", table_name="research_tasks")
    op.drop_index("ix_research_tasks_run_id", table_name="research_tasks")
    op.drop_table("research_tasks")
    op.drop_column("research_runs", "pricing_version")
    op.drop_column("research_runs", "cost_report_status")
    op.drop_column("research_runs", "usage_report_status")
    op.drop_column("research_runs", "concurrency_limit")
    op.drop_column("research_runs", "termination_reason")
    bind = op.get_bind()
    op.execute(
        "UPDATE research_runs SET consumed_total_tokens = 0 WHERE consumed_total_tokens IS NULL"
    )
    op.alter_column("research_runs", "consumed_total_tokens", nullable=False, server_default="0")
    for name in (
        "cost_report_status",
        "usage_report_status",
        "research_job_status",
        "research_job_type",
        "research_task_status",
    ):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
