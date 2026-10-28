"""Phase 10 plans and upgrade intent events.

Revision ID: 0025
Revises: 0024
"""

import sqlalchemy as sa

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_plans",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("paid_sme", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_plans_trial_ends_at", "user_plans", ["trial_ends_at"])
    op.create_table(
        "upgrade_tap_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("surface", sa.String(40), nullable=False),
        sa.Column("desired_tier", sa.String(20), nullable=False, server_default="sme"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_upgrade_tap_events_user_id", "upgrade_tap_events", ["user_id"])
    op.create_index("ix_upgrade_tap_events_occurred_at", "upgrade_tap_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_upgrade_tap_events_occurred_at", table_name="upgrade_tap_events")
    op.drop_index("ix_upgrade_tap_events_user_id", table_name="upgrade_tap_events")
    op.drop_table("upgrade_tap_events")
    op.drop_index("ix_user_plans_trial_ends_at", table_name="user_plans")
    op.drop_table("user_plans")
