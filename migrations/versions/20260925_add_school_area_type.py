# -*- coding: utf-8 -*-
"""Coluna anulável area_type em school (schemas city_%).

Escolas existentes ficam NULL. Sem valor padrão.
Códigos: urbana | rural.

Revision ID: 20260925_school_area_type
Revises: 20260921_store_item_requirement
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa


revision = "20260925_school_area_type"
down_revision = "20260921_store_item_requirement"
branch_labels = None
depends_on = None

_CHECK = "area_type IS NULL OR area_type IN ('urbana', 'rural')"


def _city_schemas_with_school(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'school' AND table_schema LIKE 'city_%' "
            "ORDER BY table_schema"
        )
    )
    return [row[0] for row in rows]


def _column_exists(conn, schema, column_name):
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'school' "
            "AND column_name = :col"
        ),
        {"schema": schema, "col": column_name},
    ).scalar()
    return row is not None


def _constraint_exists(conn, schema):
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_constraint c "
            "JOIN pg_namespace n ON n.oid = c.connamespace "
            "WHERE n.nspname = :schema AND c.conname = 'ck_school_area_type'"
        ),
        {"schema": schema},
    ).scalar()
    return row is not None


def upgrade():
    conn = op.get_bind()
    for schema in _city_schemas_with_school(conn):
        if not _column_exists(conn, schema, "area_type"):
            conn.execute(
                sa.text(
                    f'ALTER TABLE "{schema}".school '
                    "ADD COLUMN area_type VARCHAR(20)"
                )
            )
        if not _constraint_exists(conn, schema):
            conn.execute(
                sa.text(
                    f'ALTER TABLE "{schema}".school '
                    f"ADD CONSTRAINT ck_school_area_type CHECK ({_CHECK})"
                )
            )
        conn.execute(
            sa.text(
                f"COMMENT ON COLUMN \"{schema}\".school.area_type IS "
                "'Tipo de área da escola: urbana ou rural. NULL = não informado. "
                "Usado só para filtrar resultados.'"
            )
        )


def downgrade():
    conn = op.get_bind()
    for schema in _city_schemas_with_school(conn):
        if _constraint_exists(conn, schema):
            conn.execute(
                sa.text(
                    f'ALTER TABLE "{schema}".school '
                    "DROP CONSTRAINT IF EXISTS ck_school_area_type"
                )
            )
        if _column_exists(conn, schema, "area_type"):
            conn.execute(
                sa.text(f'ALTER TABLE "{schema}".school DROP COLUMN IF EXISTS area_type')
            )
