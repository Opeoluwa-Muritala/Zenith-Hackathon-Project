"""Provider links, webhook dedupe and assistant conversations.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    refresh_columns = {c["name"] for c in inspector.get_columns("refresh_tokens")}
    if "family_id" not in refresh_columns:
        op.add_column("refresh_tokens", sa.Column("family_id", sa.Uuid(), nullable=True))
        op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    if "revoked_at" not in refresh_columns:
        op.add_column("refresh_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True)))
    recurring_columns = {c["name"] for c in inspector.get_columns("recurring_series")}
    if "account_id" not in recurring_columns:
        op.add_column(
            "recurring_series",
            sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="CASCADE")),
        )
        op.create_index("ix_recurring_series_account_id", "recurring_series", ["account_id"])
    if "direction" not in recurring_columns:
        op.add_column(
            "recurring_series",
            sa.Column(
                "direction",
                sa.Enum("credit", "debit", name="direction"),
                server_default="debit",
                nullable=False,
            ),
        )
    if "provider_links" not in tables:
        op.create_table(
            "provider_links",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column(
                "consent_id",
                sa.Uuid(),
                sa.ForeignKey("consents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("provider_account_id", sa.String(200)),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("data_status", sa.String(30)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_webhook_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("provider", "provider_account_id"),
        )
        op.create_index("ix_provider_links_user_id", "provider_links", ["user_id"])
        op.create_index("ix_provider_links_consent_id", "provider_links", ["consent_id"])
    if "webhook_events" not in tables:
        op.create_table(
            "webhook_events",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("event_key", sa.String(64), nullable=False, unique=True),
            sa.Column("event_name", sa.String(100), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "assistant_conversations" not in tables:
        op.create_table(
            "assistant_conversations",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_assistant_conversations_user_id", "assistant_conversations", ["user_id"]
        )
        op.create_index(
            "ix_assistant_conversations_expires_at", "assistant_conversations", ["expires_at"]
        )
    if "assistant_messages" not in tables:
        op.create_table(
            "assistant_messages",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "conversation_id",
                sa.Uuid(),
                sa.ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content_redacted", sa.Text(), nullable=False),
            sa.Column("tool_names", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_assistant_messages_conversation_id", "assistant_messages", ["conversation_id"]
        )


def downgrade():
    for table in (
        "assistant_messages",
        "assistant_conversations",
        "webhook_events",
        "provider_links",
    ):
        op.drop_table(table)
    op.drop_column("recurring_series", "account_id")
    op.drop_column("recurring_series", "direction")
    op.drop_column("refresh_tokens", "revoked_at")
    op.drop_column("refresh_tokens", "family_id")
