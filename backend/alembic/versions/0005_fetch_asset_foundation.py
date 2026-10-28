"""Add discovered accounts, manual assets and FX rates."""

import sqlalchemy as sa

from alembic import context, op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _table_exists(name):
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade():
    if context.is_offline_mode():
        return
    if not _table_exists("discovered_accounts"):
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
            sa.Column(
                "status",
                sa.Enum("discovered", "linked", "skipped", name="discoveredaccountstatus"),
                nullable=False,
                server_default="discovered",
            ),
            sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "provider", "provider_account_id"),
        )
        op.create_index("ix_discovered_accounts_user_id", "discovered_accounts", ["user_id"])
    if not _table_exists("manual_assets"):
        op.create_table(
            "manual_assets",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column(
                "platform",
                sa.Enum(
                    "risevest",
                    "cowrywise",
                    "bamboo",
                    "chaka",
                    "real_estate",
                    "custom_cash_vault",
                    name="manualassetplatform",
                ),
                nullable=False,
            ),
            sa.Column(
                "category",
                sa.Enum(
                    "mutual_funds",
                    "us_equities",
                    "real_estate",
                    "dollar_savings",
                    "eurobonds",
                    name="manualassetcategory",
                ),
                nullable=False,
            ),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("amount_minor", sa.BigInteger(), nullable=False),
            sa.Column("fx_rate_used", sa.BigInteger()),
            sa.Column(
                "update_cadence",
                sa.Enum("biweekly", "monthly", name="updatecadence"),
                nullable=False,
            ),
            sa.Column("last_updated_at", sa.DateTime(timezone=True)),
            sa.Column("next_reminder_at", sa.DateTime(timezone=True)),
        )
        op.create_index("ix_manual_assets_user_id", "manual_assets", ["user_id"])
    if not _table_exists("fx_rates"):
        op.create_table(
            "fx_rates",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("base", sa.String(3), nullable=False),
            sa.Column("quote", sa.String(3), nullable=False),
            sa.Column("rate", sa.BigInteger(), nullable=False),
            sa.Column("source", sa.String(80), nullable=False),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade():
    if context.is_offline_mode():
        return
    for table in ("fx_rates", "manual_assets", "discovered_accounts"):
        if _table_exists(table):
            op.drop_table(table)
