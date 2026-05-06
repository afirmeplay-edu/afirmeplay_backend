# -*- coding: utf-8 -*-
"""Add public.mobile_offline_pack_registry (índice code_hash -> city_id, pack_id)

Revision ID: add_mobile_offline_pack_registry
Revises: add_city_branding_urls
Create Date: 2026-03-31

Idempotente: cria tabela apenas se não existir.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_mobile_offline_pack_registry"
down_revision = "add_city_branding_urls"
branch_labels = None
depends_on = None


def _table_exists(connection, schema, table_name):
    r = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name"
        ),
        {"schema": schema, "name": table_name},
    )
    return r.scalar() is not None


def upgrade():
    conn = op.get_bind()
    if _table_exists(conn, "public", "mobile_offline_pack_registry"):
        return

    op.create_table(
        "mobile_offline_pack_registry",
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("city_id", sa.String(), nullable=False),
        sa.Column("pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["public.city.id"],
        ),
        sa.PrimaryKeyConstraint("code_hash"),
        schema="public",
    )
    op.create_index(
        "idx_mobile_offline_pack_registry_city",
        "mobile_offline_pack_registry",
        ["city_id"],
        schema="public",
    )


def downgrade():
    conn = op.get_bind()
    if not _table_exists(conn, "public", "mobile_offline_pack_registry"):
        return
    op.drop_index(
        "idx_mobile_offline_pack_registry_city",
        table_name="mobile_offline_pack_registry",
        schema="public",
    )
    op.drop_table("mobile_offline_pack_registry", schema="public")
