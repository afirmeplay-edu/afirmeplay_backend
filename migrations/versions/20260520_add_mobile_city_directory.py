# -*- coding: utf-8 -*-
"""Add public.mobile_city_directory (catálogo mobile tenant discovery)

Revision ID: add_mobile_city_directory
Revises: 7d28dc77edf9
Create Date: 2026-05-20

Idempotente: cria tabela e seeds apenas se não existirem.
"""
from alembic import op
import sqlalchemy as sa

revision = "add_mobile_city_directory"
down_revision = "7d28dc77edf9"
branch_labels = None
depends_on = None

# Seeds estáveis (reexecução segura via ON CONFLICT)
_SEED_AFR_ID = "a1b2c3d4-e5f6-4789-a012-000000000001"
_SEED_LIM_ID = "b2c3d4e5-f6a7-4890-b123-000000000002"


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
    if not _table_exists(conn, "public", "mobile_city_directory"):
        op.create_table(
            "mobile_city_directory",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("city_name", sa.String(length=200), nullable=False),
            sa.Column("city_slug", sa.String(length=100), nullable=False),
            sa.Column("tenant_code", sa.String(length=32), nullable=False),
            sa.Column("api_base_url", sa.String(length=500), nullable=False),
            sa.Column("hosting_mode", sa.String(length=20), nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "mobile_visible",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.CheckConstraint(
                "hosting_mode IN ('shared', 'dedicated')",
                name="ck_mobile_city_directory_hosting_mode",
            ),
            sa.PrimaryKeyConstraint("id"),
            schema="public",
        )
        op.create_index(
            "uq_mobile_city_directory_city_slug",
            "mobile_city_directory",
            ["city_slug"],
            unique=True,
            schema="public",
        )
        op.create_index(
            "uq_mobile_city_directory_tenant_code",
            "mobile_city_directory",
            ["tenant_code"],
            unique=True,
            schema="public",
        )
        op.create_index(
            "idx_mobile_city_directory_mobile_list",
            "mobile_city_directory",
            ["mobile_visible", "is_active", "sort_order"],
            schema="public",
        )

    conn.execute(
        sa.text(
            """
            INSERT INTO public.mobile_city_directory (
                id, city_name, city_slug, tenant_code, api_base_url,
                hosting_mode, is_active, mobile_visible, sort_order
            ) VALUES (
                :id, :city_name, :city_slug, :tenant_code, :api_base_url,
                :hosting_mode, true, true, :sort_order
            )
            ON CONFLICT (city_slug) DO NOTHING
            """
        ),
        {
            "id": _SEED_AFR_ID,
            "city_name": "Afirme Play (VPS central)",
            "city_slug": "afirme",
            "tenant_code": "AFR001",
            "api_base_url": "https://prod-api.afirmeplay.com.br",
            "hosting_mode": "shared",
            "sort_order": 0,
        },
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO public.mobile_city_directory (
                id, city_name, city_slug, tenant_code, api_base_url,
                hosting_mode, is_active, mobile_visible, sort_order
            ) VALUES (
                :id, :city_name, :city_slug, :tenant_code, :api_base_url,
                :hosting_mode, true, true, :sort_order
            )
            ON CONFLICT (city_slug) DO NOTHING
            """
        ),
        {
            "id": _SEED_LIM_ID,
            "city_name": "Limoeiro de Anadia",
            "city_slug": "limoeirodeanadia",
            "tenant_code": "LIM001",
            "api_base_url": "https://api.afirmeplay.com.br",
            "hosting_mode": "dedicated",
            "sort_order": 10,
        },
    )


def downgrade():
    conn = op.get_bind()
    if not _table_exists(conn, "public", "mobile_city_directory"):
        return
    op.drop_index(
        "idx_mobile_city_directory_mobile_list",
        table_name="mobile_city_directory",
        schema="public",
    )
    op.drop_index(
        "uq_mobile_city_directory_tenant_code",
        table_name="mobile_city_directory",
        schema="public",
    )
    op.drop_index(
        "uq_mobile_city_directory_city_slug",
        table_name="mobile_city_directory",
        schema="public",
    )
    op.drop_table("mobile_city_directory", schema="public")
