"""Record transaction ingestion source and parser confidence."""

import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions", sa.Column("source", sa.String(20), nullable=False, server_default="mono")
    )
    op.add_column(
        "transactions",
        sa.Column("parse_confidence_bps", sa.Integer(), nullable=False, server_default="10000"),
    )


def downgrade() -> None:
    op.drop_column("transactions", "parse_confidence_bps")
    op.drop_column("transactions", "source")
