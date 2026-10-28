"""Track webhook processing without retaining financial webhook payloads."""

import sqlalchemy as sa

from alembic import context, op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    fields = (
        ("processing_status", sa.String(20), "VARCHAR(20) NOT NULL DEFAULT 'pending'"),
        ("processing_started_at", sa.DateTime(timezone=True), "TIMESTAMP WITH TIME ZONE"),
        ("processing_token", sa.String(36), "VARCHAR(36)"),
        ("processed_at", sa.DateTime(timezone=True), "TIMESTAMP WITH TIME ZONE"),
    )
    if context.is_offline_mode():
        for name, _, sql_type in fields:
            op.execute(f"ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS {name} {sql_type}")
        return
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("webhook_events")}
    for name, field_type, _ in fields:
        if name not in columns:
            op.add_column(
                "webhook_events",
                sa.Column(
                    name,
                    field_type,
                    nullable=name != "processing_status",
                    server_default="pending" if name == "processing_status" else None,
                ),
            )


def downgrade():
    for name in ("processed_at", "processing_token", "processing_started_at", "processing_status"):
        if context.is_offline_mode():
            op.execute(f"ALTER TABLE webhook_events DROP COLUMN IF EXISTS {name}")
        else:
            op.drop_column("webhook_events", name)
