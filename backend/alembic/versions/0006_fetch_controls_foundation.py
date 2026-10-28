"""Add category rules, budgets, device tokens and notification preferences."""

import sqlalchemy as sa

from alembic import context, op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _table_exists(name):
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade():
    if context.is_offline_mode():
        return
    if not _table_exists("category_rules"):
        op.create_table(
            "category_rules",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("counterparty_key", sa.String(160), nullable=False),
            sa.Column("category", sa.String(40), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "counterparty_key"),
        )
        op.create_index("ix_category_rules_user_id", "category_rules", ["user_id"])
    if not _table_exists("budgets"):
        op.create_table(
            "budgets",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("monthly_limit_minor", sa.BigInteger(), nullable=False),
            sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_budgets_user_id", "budgets", ["user_id"])
    if not _table_exists("device_tokens"):
        op.create_table(
            "device_tokens",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("platform", sa.String(20), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_device_tokens_user_id", "device_tokens", ["user_id"])
    if not _table_exists("notification_preferences"):
        op.create_table(
            "notification_preferences",
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "overspending_alerts", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "loan_repayment_reminders", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "investment_update_prompts", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
        )


def downgrade():
    if context.is_offline_mode():
        return
    for table in ("notification_preferences", "device_tokens", "budgets", "category_rules"):
        if _table_exists(table):
            op.drop_table(table)
