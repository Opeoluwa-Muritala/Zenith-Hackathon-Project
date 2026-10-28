"""Keep institution mapping and hosted-link reference on discovered accounts."""

import sqlalchemy as sa

from alembic import context, op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        return
    columns = {
        item["name"] for item in sa.inspect(op.get_bind()).get_columns("discovered_accounts")
    }
    if "institution_id" not in columns:
        op.add_column("discovered_accounts", sa.Column("institution_id", sa.String(80)))
    if "institution_auth_method" not in columns:
        op.add_column("discovered_accounts", sa.Column("institution_auth_method", sa.String(40)))
    if "link_ref" not in columns:
        op.add_column("discovered_accounts", sa.Column("link_ref", sa.String(80)))
        op.create_unique_constraint(
            "uq_discovered_accounts_link_ref", "discovered_accounts", ["link_ref"]
        )
    if "account_match_requested" not in columns:
        op.add_column(
            "discovered_accounts",
            sa.Column(
                "account_match_requested", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )


def downgrade():
    if context.is_offline_mode():
        return
    columns = {
        item["name"] for item in sa.inspect(op.get_bind()).get_columns("discovered_accounts")
    }
    if "account_match_requested" in columns:
        op.drop_column("discovered_accounts", "account_match_requested")
    if "link_ref" in columns:
        uniques = sa.inspect(op.get_bind()).get_unique_constraints("discovered_accounts")
        for item in uniques:
            if item["column_names"] == ["link_ref"] and item["name"]:
                op.drop_constraint(item["name"], "discovered_accounts", type_="unique")
        op.drop_column("discovered_accounts", "link_ref")
    if "institution_auth_method" in columns:
        op.drop_column("discovered_accounts", "institution_auth_method")
    if "institution_id" in columns:
        op.drop_column("discovered_accounts", "institution_id")
