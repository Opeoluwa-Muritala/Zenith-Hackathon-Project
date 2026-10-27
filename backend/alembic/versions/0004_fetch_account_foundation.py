"""Add account and transaction fields required by the Fetch foundation."""

import sqlalchemy as sa

from alembic import context, op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _columns(table):
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if context.is_offline_mode():
        return
    account_columns = _columns("accounts")
    if "category" not in account_columns:
        category_type = sa.Enum(
            "commercial_bank",
            "digital_bank_wallet",
            "investment",
            "loan_credit",
            name="accountcategory",
        )
        category_type.create(op.get_bind(), checkfirst=True)
        op.add_column(
            "accounts",
            sa.Column(
                "category",
                category_type,
                nullable=False,
                server_default="commercial_bank",
            ),
        )
    for name, column in (
        ("available_balance_minor", sa.Column("available_balance_minor", sa.BigInteger())),
        ("ledger_balance_minor", sa.Column("ledger_balance_minor", sa.BigInteger())),
        ("balance_synced_at", sa.Column("balance_synced_at", sa.DateTime(timezone=True))),
        (
            "sync_status",
            sa.Column(
                "sync_status",
                sa.Enum("ok", "delayed", "error", name="syncstatus"),
                nullable=False,
                server_default="ok",
            ),
        ),
        (
            "sync_paused",
            sa.Column("sync_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        ),
    ):
        if name not in account_columns:
            if name == "sync_status":
                column.type.create(op.get_bind(), checkfirst=True)
            op.add_column("accounts", column)

    transaction_columns = _columns("transactions")
    if "decoded_merchant" not in transaction_columns:
        op.add_column("transactions", sa.Column("decoded_merchant", sa.String(100)))
    if "category_source" not in transaction_columns:
        source_type = sa.Enum("auto", "user_rule", "manual", name="categorysource")
        source_type.create(op.get_bind(), checkfirst=True)
        op.add_column(
            "transactions",
            sa.Column(
                "category_source",
                source_type,
                nullable=False,
                server_default="auto",
            ),
        )


def downgrade():
    if context.is_offline_mode():
        return
    transaction_columns = _columns("transactions")
    if "category_source" in transaction_columns:
        op.drop_column("transactions", "category_source")
    if "decoded_merchant" in transaction_columns:
        op.drop_column("transactions", "decoded_merchant")

    account_columns = _columns("accounts")
    for name in (
        "sync_paused",
        "sync_status",
        "balance_synced_at",
        "ledger_balance_minor",
        "available_balance_minor",
        "category",
    ):
        if name in account_columns:
            op.drop_column("accounts", name)
    for enum_type in (
        sa.Enum(name="categorysource"),
        sa.Enum(name="syncstatus"),
        sa.Enum(name="accountcategory"),
    ):
        enum_type.drop(op.get_bind(), checkfirst=True)
