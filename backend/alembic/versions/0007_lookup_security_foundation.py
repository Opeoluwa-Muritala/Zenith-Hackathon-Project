"""Encrypt push/account fields and add BVN Lookup sessions."""

import sqlalchemy as sa

from alembic import context, op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _columns(table):
    return {x["name"] for x in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if context.is_offline_mode():
        return
    device_columns = _columns("device_tokens")
    if "token_encrypted" not in device_columns:
        op.add_column("device_tokens", sa.Column("token_encrypted", sa.String(512), nullable=True))

    existing_rows = (
        op.get_bind().execute(sa.text("SELECT COUNT(*) FROM discovered_accounts")).scalar_one()
    )
    if existing_rows:
        raise RuntimeError(
            "Migration 0007 cannot reconstruct existing discovered account numbers; "
            "export and migrate these rows safely before upgrading"
        )
    op.drop_table("discovered_accounts")
    op.create_table(
        "discovered_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("account_name", sa.String(160), nullable=False),
        sa.Column("account_designation", sa.String(40), nullable=False),
        sa.Column("bank_code", sa.String(10), nullable=False),
        sa.Column("nip_code", sa.String(10)),
        sa.Column("institution_name", sa.String(120), nullable=False),
        sa.Column("account_type", sa.String(40), nullable=False),
        sa.Column("account_number_encrypted", sa.String(512), nullable=False),
        sa.Column("account_number_last4", sa.String(4), nullable=False),
        sa.Column("account_number_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="discovered"),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "bank_code", "account_number_hash"),
    )
    op.create_index("ix_discovered_accounts_user_id", "discovered_accounts", ["user_id"])

    if "bvn_lookup_sessions" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "bvn_lookup_sessions",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("mono_session_id", sa.String(100), nullable=False, unique=True),
            sa.Column("scope", sa.String(30), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="initiated"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_bvn_lookup_sessions_user_id", "bvn_lookup_sessions", ["user_id"])
        op.create_index("ix_bvn_lookup_sessions_expires_at", "bvn_lookup_sessions", ["expires_at"])


def downgrade():
    if context.is_offline_mode():
        return
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM discovered_accounts")).scalar_one():
        raise RuntimeError("Downgrade 0007 would discard discovered accounts")
    op.drop_table("bvn_lookup_sessions")
    op.drop_table("discovered_accounts")
    op.create_table(
        "discovered_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_account_id", sa.String(200), nullable=False),
        sa.Column("institution", sa.String(80), nullable=False),
        sa.Column("account_type", sa.String(40), nullable=False),
        sa.Column("masked_number", sa.String(20), nullable=False),
        sa.Column("balance_minor", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="discovered"),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "provider", "provider_account_id"),
    )
    op.create_index("ix_discovered_accounts_user_id", "discovered_accounts", ["user_id"])
    if "token_encrypted" in _columns("device_tokens"):
        op.drop_column("device_tokens", "token_encrypted")
