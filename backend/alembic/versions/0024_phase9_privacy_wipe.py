"""Phase 9 durable unlink queue and minimal wipe audit.

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_unlinks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_hash", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_account_id_encrypted", sa.String(512), nullable=False),
        sa.Column("provider_account_id_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "provider_account_id_hash"),
    )
    op.create_index("ix_pending_unlinks_user_hash", "pending_unlinks", ["user_hash"])
    op.create_index("ix_pending_unlinks_completed_at", "pending_unlinks", ["completed_at"])
    op.create_table(
        "wipe_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_hash", sa.String(64), nullable=False),
        sa.Column("wiped_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_wipe_audits_user_hash", "wipe_audits", ["user_hash"])
    op.create_index("ix_wipe_audits_wiped_at", "wipe_audits", ["wiped_at"])


def downgrade() -> None:
    op.drop_index("ix_wipe_audits_wiped_at", table_name="wipe_audits")
    op.drop_index("ix_wipe_audits_user_hash", table_name="wipe_audits")
    op.drop_table("wipe_audits")
    op.drop_index("ix_pending_unlinks_completed_at", table_name="pending_unlinks")
    op.drop_index("ix_pending_unlinks_user_hash", table_name="pending_unlinks")
    op.drop_table("pending_unlinks")
