"""Persist the successful per-account sync cursor."""

import sqlalchemy as sa

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("sync_cursor_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("accounts", "sync_cursor_at")
