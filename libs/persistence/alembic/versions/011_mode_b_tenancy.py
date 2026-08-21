"""Mode B principals, sessions, credential vault, and ownership.

Revision ID: 011
Revises: 010
Create Date: 2026-08-21

"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOCAL_SYSTEM_ID = UUID("00000000-0000-4000-a000-000000000001")


def upgrade() -> None:
    op.create_table(
        "principals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=320)),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("avatar_url", sa.String(length=2048)),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO principals (id, kind, display_name, status) "
            "VALUES (:id, 'local_system', 'Local operator', 'active')"
        ).bindparams(id=LOCAL_SYSTEM_ID)
    )
    op.create_table(
        "auth_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("principals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "provider_account_id", name="uq_auth_accounts_provider_subject"),
    )
    op.create_index("ix_auth_accounts_principal_id", "auth_accounts", ["principal_id"])
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("principals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_auth_sessions_principal_id", "auth_sessions", ["principal_id"])
    op.create_table(
        "oauth_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("state", sa.String(length=128), nullable=False, unique=True),
        sa.Column("code_verifier", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("next_path", sa.String(length=256), nullable=False, server_default="/"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "provider_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("principals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="configured"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("principal_id", "provider", name="uq_provider_credentials_principal_provider"),
    )
    op.create_index("ix_provider_credentials_principal_id", "provider_credentials", ["principal_id"])
    op.create_table(
        "auth_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("principals.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_auth_events_principal_id", "auth_events", ["principal_id"])

    op.add_column("research_runs", sa.Column("owner_principal_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("research_runs", sa.Column("is_public_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("research_runs", sa.Column("public_slug", sa.String(length=80), nullable=True))
    op.create_unique_constraint("uq_research_runs_public_slug", "research_runs", ["public_slug"])
    op.create_foreign_key(
        "fk_research_runs_owner",
        "research_runs",
        "principals",
        ["owner_principal_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_research_runs_owner_principal_id", "research_runs", ["owner_principal_id"])
    op.execute(sa.text("UPDATE research_runs SET owner_principal_id = :id").bindparams(id=LOCAL_SYSTEM_ID))

    op.add_column("research_templates", sa.Column("owner_principal_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_research_templates_owner",
        "research_templates",
        "principals",
        ["owner_principal_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(sa.text("UPDATE research_templates SET owner_principal_id = :id").bindparams(id=LOCAL_SYSTEM_ID))

    op.add_column("research_monitors", sa.Column("owner_principal_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_research_monitors_owner",
        "research_monitors",
        "principals",
        ["owner_principal_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(sa.text("UPDATE research_monitors SET owner_principal_id = :id").bindparams(id=LOCAL_SYSTEM_ID))


def downgrade() -> None:
    op.drop_constraint("fk_research_monitors_owner", "research_monitors", type_="foreignkey")
    op.drop_column("research_monitors", "owner_principal_id")
    op.drop_constraint("fk_research_templates_owner", "research_templates", type_="foreignkey")
    op.drop_column("research_templates", "owner_principal_id")
    op.drop_index("ix_research_runs_owner_principal_id", table_name="research_runs")
    op.drop_constraint("fk_research_runs_owner", "research_runs", type_="foreignkey")
    op.drop_constraint("uq_research_runs_public_slug", "research_runs", type_="unique")
    op.drop_column("research_runs", "public_slug")
    op.drop_column("research_runs", "is_public_demo")
    op.drop_column("research_runs", "owner_principal_id")
    op.drop_table("auth_events")
    op.drop_table("provider_credentials")
    op.drop_table("oauth_states")
    op.drop_table("auth_sessions")
    op.drop_table("auth_accounts")
    op.drop_table("principals")
