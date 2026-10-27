"""Encrypt stored Mono account identifiers while preserving indexed lookup."""

import sqlalchemy as sa

from alembic import context, op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _unique_name(columns):
    for item in sa.inspect(op.get_bind()).get_unique_constraints("provider_links"):
        if item["column_names"] == columns:
            return item["name"]
    return None


def upgrade():
    if context.is_offline_mode():
        op.execute(
            "ALTER TABLE provider_links ADD COLUMN IF NOT EXISTS "
            "provider_account_id_encrypted VARCHAR(512)"
        )
        op.execute(
            "ALTER TABLE provider_links ADD COLUMN IF NOT EXISTS "
            "provider_account_id_hash VARCHAR(64)"
        )
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                AND table_name = 'provider_links' AND column_name = 'provider_account_id') THEN
                IF EXISTS (SELECT 1 FROM provider_links WHERE provider_account_id IS NOT NULL) THEN
                    RAISE EXCEPTION 'Run online migration 0009 to encrypt existing identifiers';
                END IF;
                ALTER TABLE provider_links DROP COLUMN provider_account_id;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'provider_links'::regclass
                AND conname = 'uq_provider_links_account_hash') THEN
                ALTER TABLE provider_links ADD CONSTRAINT uq_provider_links_account_hash
                    UNIQUE (provider, provider_account_id_hash);
            END IF;
        END $$""")
        return
    from app.core.encryption import encrypt_field, hash_field

    connection = op.get_bind()
    columns = {item["name"] for item in sa.inspect(connection).get_columns("provider_links")}
    if "provider_account_id_encrypted" not in columns:
        op.add_column("provider_links", sa.Column("provider_account_id_encrypted", sa.String(512)))
    if "provider_account_id_hash" not in columns:
        op.add_column("provider_links", sa.Column("provider_account_id_hash", sa.String(64)))
    if "provider_account_id" in columns:
        rows = connection.execute(
            sa.text(
                "SELECT id, provider_account_id FROM provider_links "
                "WHERE provider_account_id IS NOT NULL"
            )
        )
        for row in rows:
            connection.execute(
                sa.text(
                    "UPDATE provider_links SET provider_account_id_encrypted = :encrypted, "
                    "provider_account_id_hash = :digest WHERE id = :id"
                ),
                {
                    "id": row.id,
                    "encrypted": encrypt_field(row.provider_account_id),
                    "digest": hash_field(row.provider_account_id),
                },
            )
        old_unique = _unique_name(["provider", "provider_account_id"])
        if old_unique:
            op.drop_constraint(old_unique, "provider_links", type_="unique")
        op.drop_column("provider_links", "provider_account_id")
    if not _unique_name(["provider", "provider_account_id_hash"]):
        op.create_unique_constraint(
            "uq_provider_links_account_hash",
            "provider_links",
            ["provider", "provider_account_id_hash"],
        )


def downgrade():
    if context.is_offline_mode():
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM provider_links
                WHERE provider_account_id_encrypted IS NOT NULL) THEN
                RAISE EXCEPTION 'Online downgrade 0009 required to decrypt existing identifiers';
            END IF;
        END $$""")
        op.execute(
            "ALTER TABLE provider_links ADD COLUMN IF NOT EXISTS provider_account_id VARCHAR(200)"
        )
        op.execute(
            "ALTER TABLE provider_links DROP CONSTRAINT IF EXISTS uq_provider_links_account_hash"
        )
        op.execute("ALTER TABLE provider_links DROP COLUMN IF EXISTS provider_account_id_hash")
        op.execute("ALTER TABLE provider_links DROP COLUMN IF EXISTS provider_account_id_encrypted")
        op.create_unique_constraint(
            "uq_provider_links_account_id", "provider_links", ["provider", "provider_account_id"]
        )
        return
    from app.core.encryption import decrypt_field

    connection = op.get_bind()
    columns = {item["name"] for item in sa.inspect(connection).get_columns("provider_links")}
    if "provider_account_id" not in columns:
        op.add_column("provider_links", sa.Column("provider_account_id", sa.String(200)))
    rows = connection.execute(
        sa.text(
            "SELECT id, provider_account_id_encrypted FROM provider_links "
            "WHERE provider_account_id_encrypted IS NOT NULL"
        )
    )
    for row in rows:
        connection.execute(
            sa.text("UPDATE provider_links SET provider_account_id = :value WHERE id = :id"),
            {"id": row.id, "value": decrypt_field(row.provider_account_id_encrypted)},
        )
    new_unique = _unique_name(["provider", "provider_account_id_hash"])
    if new_unique:
        op.drop_constraint(new_unique, "provider_links", type_="unique")
    if not _unique_name(["provider", "provider_account_id"]):
        op.create_unique_constraint(
            "uq_provider_links_account_id", "provider_links", ["provider", "provider_account_id"]
        )
    op.drop_column("provider_links", "provider_account_id_hash")
    op.drop_column("provider_links", "provider_account_id_encrypted")
