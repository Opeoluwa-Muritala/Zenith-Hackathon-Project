"""Associate webhook processing metadata with its owning user.

Revision ID: 0026
Revises: 0025
"""

import sqlalchemy as sa

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("webhook_events", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_webhook_events_user_id_users",
        "webhook_events",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_webhook_events_user_id", "webhook_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_webhook_events_user_id", table_name="webhook_events")
    op.drop_constraint("fk_webhook_events_user_id_users", "webhook_events", type_="foreignkey")
    op.drop_column("webhook_events", "user_id")
