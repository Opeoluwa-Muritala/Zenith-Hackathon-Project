"""Persist upcoming obligations and linked historical payments."""

import sqlalchemy as sa

from alembic import context, op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        return
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "obligations" not in tables:
        op.create_table(
            "obligations",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
            sa.Column("lender_name", sa.String(120), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("amount_minor", sa.BigInteger(), nullable=False),
            sa.Column("cadence_days", sa.Integer(), nullable=False),
            sa.Column("next_due_date", sa.Date(), nullable=False),
            sa.Column("confidence_bps", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("source", sa.String(20), nullable=False),
            sa.UniqueConstraint("user_id", "account_id", "lender_name", "kind", "source"),
        )
        op.create_index("ix_obligations_user_id", "obligations", ["user_id"])
    if "obligation_payments" not in tables:
        op.create_table(
            "obligation_payments",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "obligation_id",
                sa.Uuid(),
                sa.ForeignKey("obligations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "transaction_id",
                sa.Uuid(),
                sa.ForeignKey("transactions.id", ondelete="SET NULL"),
                unique=True,
            ),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        )
        op.create_index(
            "ix_obligation_payments_obligation_id", "obligation_payments", ["obligation_id"]
        )


def downgrade():
    if context.is_offline_mode():
        return
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "obligation_payments" in tables:
        op.drop_table("obligation_payments")
    if "obligations" in tables:
        op.drop_table("obligations")
