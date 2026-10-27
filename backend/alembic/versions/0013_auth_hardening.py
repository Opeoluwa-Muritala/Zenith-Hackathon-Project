"""Add durable OTP lockouts and metadata-only security audit events."""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_lockouts",
        sa.Column("identifier_hash", sa.String(64), primary_key=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_lockouts_locked_until", "auth_lockouts", ["locked_until"])
    op.create_table(
        "security_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("subject_hash", sa.String(64)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_security_audit_events_user_id", "security_audit_events", ["user_id"])
    op.create_index("ix_security_audit_events_event", "security_audit_events", ["event"])
    op.create_index(
        "ix_security_audit_events_subject_hash", "security_audit_events", ["subject_hash"]
    )
    op.create_index(
        "ix_security_audit_events_occurred_at", "security_audit_events", ["occurred_at"]
    )


def downgrade() -> None:
    op.drop_table("security_audit_events")
    op.drop_table("auth_lockouts")
