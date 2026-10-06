"""AI preference, insight wording metadata and metadata-only audit.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    settings_columns = {c["name"] for c in inspector.get_columns("user_settings")}
    if "ai_enabled" not in settings_columns:
        op.add_column(
            "user_settings",
            sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    insight_columns = {c["name"] for c in inspector.get_columns("insights")}
    for name, column in (
        (
            "template_title",
            sa.Column("template_title", sa.String(160), nullable=False, server_default=""),
        ),
        ("template_body", sa.Column("template_body", sa.Text(), nullable=False, server_default="")),
        (
            "wording_source",
            sa.Column("wording_source", sa.String(12), nullable=False, server_default="template"),
        ),
        ("prompt_version", sa.Column("prompt_version", sa.String(40))),
        ("wording_cache_key", sa.Column("wording_cache_key", sa.String(64))),
    ):
        if name not in insight_columns:
            op.add_column("insights", column)
    if "wording_cache_key" not in insight_columns:
        op.create_index("ix_insights_wording_cache_key", "insights", ["wording_cache_key"])
    if "ai_audit" not in inspector.get_table_names():
        op.create_table(
            "ai_audit",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("feature", sa.String(12), nullable=False),
            sa.Column("model", sa.String(100), nullable=False),
            sa.Column("prompt_version", sa.String(40), nullable=False),
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "verification_passed", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("tools_used", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_ai_audit_user_id", "ai_audit", ["user_id"])
        op.create_index("ix_ai_audit_created_at", "ai_audit", ["created_at"])


def downgrade():
    op.drop_table("ai_audit")
    op.drop_index("ix_insights_wording_cache_key", table_name="insights")
    for name in (
        "wording_cache_key",
        "prompt_version",
        "wording_source",
        "template_body",
        "template_title",
    ):
        op.drop_column("insights", name)
    op.drop_column("user_settings", "ai_enabled")
