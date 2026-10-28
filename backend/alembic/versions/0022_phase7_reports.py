"""Add revocable report links and one bookkeeper invite."""

import sqlalchemy as sa

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_share_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_report_share_links_user_id", "report_share_links", ["user_id"])
    op.create_index("ix_report_share_links_expires_at", "report_share_links", ["expires_at"])
    op.create_table(
        "bookkeeper_invites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "accepted_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_bookkeeper_invites_owner_user_id", "bookkeeper_invites", ["owner_user_id"])
    op.create_index(
        "ix_bookkeeper_invites_accepted_by_user_id",
        "bookkeeper_invites",
        ["accepted_by_user_id"],
    )
    op.create_index("ix_bookkeeper_invites_expires_at", "bookkeeper_invites", ["expires_at"])


def downgrade() -> None:
    op.drop_table("bookkeeper_invites")
    op.drop_table("report_share_links")
