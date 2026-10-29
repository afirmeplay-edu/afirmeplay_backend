# -*- coding: utf-8 -*-
"""Aplicador, origem e edição manual em logistics_schedule_item (city_%).

Itens que já existem ficam origem 'manual' e editado_manualmente false.
Não cria nem apaga cronogramas.

Revision ID: 20261029_logistics_applicator
Revises: 20261023_question_origin
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa

from app.services.city_schema_service import get_logistics_item_applicator_columns_ddl


revision = "20261029_logistics_applicator"
down_revision = "20261023_question_origin"
branch_labels = None
depends_on = None


def _schemas_with_item_table(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'logistics_schedule_item' "
            "AND table_schema LIKE 'city_%' "
            "ORDER BY table_schema"
        )
    )
    return [row[0] for row in rows]


def _dbapi_cursor(conn):
    raw = conn.connection
    cursor = raw.cursor() if hasattr(raw, "cursor") else raw.dbapi_connection.cursor()
    return cursor


def upgrade():
    conn = op.get_bind()
    schemas = _schemas_with_item_table(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(get_logistics_item_applicator_columns_ddl(schema))
    finally:
        cursor.close()


def downgrade():
    conn = op.get_bind()
    schemas = _schemas_with_item_table(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(
                f'''
                ALTER TABLE "{schema}".logistics_schedule_item
                    DROP CONSTRAINT IF EXISTS fk_logistics_item_applicator_user;
                ALTER TABLE "{schema}".logistics_schedule_item
                    DROP CONSTRAINT IF EXISTS ck_logistics_item_origem;
                DROP INDEX IF EXISTS "{schema}".idx_logistics_item_applicator_user_id;
                ALTER TABLE "{schema}".logistics_schedule_item
                    DROP COLUMN IF EXISTS applicator_user_id;
                ALTER TABLE "{schema}".logistics_schedule_item
                    DROP COLUMN IF EXISTS origem;
                ALTER TABLE "{schema}".logistics_schedule_item
                    DROP COLUMN IF EXISTS editado_manualmente;
                '''
            )
    finally:
        cursor.close()
