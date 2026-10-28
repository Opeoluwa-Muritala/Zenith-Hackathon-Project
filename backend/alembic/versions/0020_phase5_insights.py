"""Add Phase 5 insight profiles, SME labels and alerts."""

import sqlalchemy as sa

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "insight_profiles",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("mode", sa.String(12), nullable=False, server_default="consumer"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('consumer', 'sme')", name="ck_insight_profiles_mode"),
    )
    op.create_table(
        "transaction_use_labels",
        sa.Column(
            "transaction_id",
            sa.Uuid(),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("suggested_label", sa.String(12), nullable=False),
        sa.Column("confidence_bps", sa.Integer(), nullable=False),
        sa.Column("confirmed_label", sa.String(12)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "suggested_label IN ('business', 'personal', 'unsure')",
            name="ck_transaction_use_suggested",
        ),
        sa.CheckConstraint(
            "confirmed_label IS NULL OR confirmed_label IN ('business', 'personal', 'unsure')",
            name="ck_transaction_use_confirmed",
        ),
        sa.CheckConstraint(
            "confidence_bps BETWEEN 0 AND 10000", name="ck_transaction_use_confidence"
        ),
    )
    op.create_index("ix_transaction_use_labels_user_id", "transaction_use_labels", ["user_id"])
    op.create_table(
        "insight_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "insight_id",
            sa.Uuid(),
            sa.ForeignKey("insights.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("what_changed", sa.String(200), nullable=False),
        sa.Column("suggested_response", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "insight_id"),
    )
    op.create_index("ix_insight_alerts_user_id", "insight_alerts", ["user_id"])
    op.create_index("ix_insight_alerts_insight_id", "insight_alerts", ["insight_id"])


def downgrade() -> None:
    op.drop_table("insight_alerts")
    op.drop_table("transaction_use_labels")
    op.drop_table("insight_profiles")
