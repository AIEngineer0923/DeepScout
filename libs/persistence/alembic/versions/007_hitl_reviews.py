"""HITL review requests, audit events, and human evaluation feedback.

Revision ID: 007
Revises: 006
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    enums = {
        "review_reason_code": (
            "budget_extension",
            "privileged_tool",
            "external_write",
            "destructive_operation",
            "global_knowledge_promotion",
            "knowledge_deletion",
            "security_sensitive_action",
            "manual_user_request",
            "human_input_required",
        ),
        "review_risk_level": ("low", "medium", "high", "critical"),
        "review_request_status": (
            "pending",
            "approved",
            "edited",
            "rejected",
            "responded",
            "expired",
            "cancelled",
            "superseded",
        ),
        "review_decision_kind": ("approve", "edit", "reject", "respond"),
        "human_feedback_target": ("report", "claim", "evidence", "retrieval", "overall"),
    }
    created: dict[str, postgresql.ENUM] = {}
    for name, values in enums.items():
        enum = postgresql.ENUM(*values, name=name, create_type=False)
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
        created[name] = enum

    op.create_table(
        "review_requests",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("research_task_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("reason_code", created["review_reason_code"], nullable=False),
        sa.Column("risk_level", created["review_risk_level"], nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("proposed_action_type", sa.String(length=64), nullable=False),
        sa.Column(
            "proposed_action_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            created["review_request_status"],
            nullable=False,
            server_default="pending",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("policy_version", sa.String(length=32), nullable=False, server_default="hitl-v1"),
        sa.Column("created_by_component", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=128), nullable=True),
        sa.Column("resolved_source", sa.String(length=32), nullable=True),
        sa.Column("decision_kind", created["review_decision_kind"], nullable=True),
        sa.Column("decision_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("rejection_outcome", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_review_requests_run_id", "review_requests", ["research_run_id"])
    op.create_index("ix_review_requests_status", "review_requests", ["status"])
    op.execute(
        "CREATE UNIQUE INDEX uq_review_pending_run_reason "
        "ON review_requests (research_run_id, reason_code) "
        "WHERE status = 'pending'"
    )

    op.create_table(
        "review_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "review_request_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("review_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_source", sa.String(length=32), nullable=False),
        sa.Column("actor_identity", sa.String(length=128), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_review_events_review_id", "review_events", ["review_request_id"])

    op.create_table(
        "human_feedback",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", created["human_feedback_target"], nullable=False),
        sa.Column("target_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="ui"),
        sa.Column(
            "created_by", sa.String(length=128), nullable=False, server_default="local_operator"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_human_feedback_run_id", "human_feedback", ["research_run_id"])


def downgrade() -> None:
    op.drop_table("human_feedback")
    op.drop_table("review_events")
    op.drop_index("uq_review_pending_run_reason", table_name="review_requests")
    op.drop_table("review_requests")
    for name in (
        "human_feedback_target",
        "review_decision_kind",
        "review_request_status",
        "review_risk_level",
        "review_reason_code",
    ):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
