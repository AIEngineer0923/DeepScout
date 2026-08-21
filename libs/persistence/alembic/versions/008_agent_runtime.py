"""Agent runtime: notes, config snapshot, skill bindings, compaction, fork lineage.

Revision ID: 008
Revises: 007
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    note_kind = postgresql.ENUM(
        "decision",
        "open_question",
        "fact_reference",
        "failed_approach",
        "next_action",
        "constraint",
        "risk",
        name="agent_note_kind",
        create_type=False,
    )
    postgresql.ENUM(
        "decision",
        "open_question",
        "fact_reference",
        "failed_approach",
        "next_action",
        "constraint",
        "risk",
        name="agent_note_kind",
    ).create(bind, checkfirst=True)

    op.add_column(
        "research_runs",
        sa.Column("config_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("research_runs", sa.Column("parent_run_id", sa.Uuid(as_uuid=True), nullable=True))
    op.add_column("research_runs", sa.Column("fork_reason", sa.String(length=128), nullable=True))
    op.add_column(
        "research_runs",
        sa.Column("replans_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_research_runs_parent",
        "research_runs",
        "research_runs",
        ["parent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "agent_notes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("research_task_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("kind", note_kind, nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("artifact_ref", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_notes_run_id", "agent_notes", ["research_run_id"])

    op.create_table(
        "run_skill_bindings",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("research_task_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("skill_id", sa.String(length=64), nullable=False),
        sa.Column("skill_version", sa.String(length=32), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_run_skill_bindings_run_id", "run_skill_bindings", ["research_run_id"])

    op.create_table(
        "context_compaction_records",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "research_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("chars_before", sa.Integer(), nullable=False),
        sa.Column("chars_after", sa.Integer(), nullable=False),
        sa.Column("dropped_redundant", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("artifact_refs_kept", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("context_compaction_records")
    op.drop_table("run_skill_bindings")
    op.drop_table("agent_notes")
    op.drop_constraint("fk_research_runs_parent", "research_runs", type_="foreignkey")
    op.drop_column("research_runs", "replans_used")
    op.drop_column("research_runs", "fork_reason")
    op.drop_column("research_runs", "parent_run_id")
    op.drop_column("research_runs", "config_snapshot")
    postgresql.ENUM(name="agent_note_kind").drop(op.get_bind(), checkfirst=True)
