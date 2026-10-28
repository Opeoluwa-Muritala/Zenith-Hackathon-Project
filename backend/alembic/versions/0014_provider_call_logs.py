"""Track billable provider calls for throttling and cost control."""

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_call_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("operation", sa.String(60), nullable=False),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
    )
    op.create_index("ix_provider_call_logs_user_id", "provider_call_logs", ["user_id"])
    op.create_index("ix_provider_call_logs_requested_at", "provider_call_logs", ["requested_at"])


def downgrade() -> None:
    op.drop_table("provider_call_logs")
