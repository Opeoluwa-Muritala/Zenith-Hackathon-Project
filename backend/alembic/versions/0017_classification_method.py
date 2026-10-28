"""Record whether transaction classification came from rules or provider data."""

import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("classification_method", sa.String(20), nullable=False, server_default="rule"))


def downgrade() -> None:
    op.drop_column("transactions", "classification_method")
