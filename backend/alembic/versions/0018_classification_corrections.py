"""Persist user classification corrections for measurable accuracy improvement."""

import sqlalchemy as sa

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "classification_corrections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("counterparty_key", sa.String(160), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_classification_corrections_user_id", "classification_corrections", ["user_id"])
    op.create_index("ix_classification_corrections_counterparty_key", "classification_corrections", ["counterparty_key"])


def downgrade() -> None:
    op.drop_table("classification_corrections")
