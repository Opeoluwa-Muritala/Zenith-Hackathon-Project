"""Store one-time code challenges and session revocation timestamps."""

import sqlalchemy as sa

from alembic import context, op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        return
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "sessions_revoked_at" not in user_columns:
        op.add_column("users", sa.Column("sessions_revoked_at", sa.DateTime(timezone=True)))
    phone_column = next(
        column for column in inspector.get_columns("users") if column["name"] == "phone"
    )
    if not phone_column["nullable"]:
        op.alter_column("users", "phone", existing_type=sa.String(20), nullable=True)
    uniques = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("users")
    }
    if ("email",) not in uniques:
        op.create_unique_constraint("uq_users_email", "users", ["email"])
    if "otp_codes" not in inspector.get_table_names():
        op.create_table(
            "otp_codes",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("identifier", sa.String(254), nullable=False),
            sa.Column("code_hash", sa.String(64), nullable=False),
            sa.Column("salt", sa.String(32), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("consumed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_otp_codes_identifier", "otp_codes", ["identifier"])


def downgrade():
    if context.is_offline_mode():
        return
    inspector = sa.inspect(op.get_bind())
    if (
        op.get_bind()
        .execute(sa.text("SELECT COUNT(*) FROM users WHERE phone IS NULL"))
        .scalar_one()
    ):
        raise RuntimeError("Cannot make phone required while email-only users exist")
    if "otp_codes" in inspector.get_table_names():
        op.drop_table("otp_codes")
    if "sessions_revoked_at" in {column["name"] for column in inspector.get_columns("users")}:
        op.drop_column("users", "sessions_revoked_at")
    if ("email",) in {tuple(c["column_names"]) for c in inspector.get_unique_constraints("users")}:
        if "uq_users_email" in {c["name"] for c in inspector.get_unique_constraints("users")}:
            op.drop_constraint("uq_users_email", "users", type_="unique")
    op.alter_column("users", "phone", existing_type=sa.String(20), nullable=False)
