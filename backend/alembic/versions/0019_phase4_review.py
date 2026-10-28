"""Add confirmation state and reviewed global classification rules."""

import sqlalchemy as sa

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transfer_suggestions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("counterparty_key", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "counterparty_key", "kind"),
    )
    op.create_index("ix_transfer_suggestions_user_id", "transfer_suggestions", ["user_id"])
    op.create_table(
        "reviewed_global_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("narration_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reviewed_global_rules")
    op.drop_table("transfer_suggestions")
