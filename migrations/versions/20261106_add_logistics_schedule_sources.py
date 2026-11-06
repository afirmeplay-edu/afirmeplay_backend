# -*- coding: utf-8 -*-
"""Origens do cronograma de logística (avaliação / cartão / personalizada).

Em logistics_schedule (city_%):
- source NOT NULL DEFAULT 'avaliacao'
- test_id passa a aceitar NULL
- gabarito_id NULL (FK answer_sheet_gabaritos ON DELETE SET NULL) + índice
- evaluation_mode NULL (virtual|physical para personalizada)
- CHECK de coerência das origens

Cronogramas existentes ficam source='avaliacao'.

Revision ID: 20261106_logistics_sources
Revises: 20261105_formation_certs
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa

from app.services.city_schema_service import get_logistics_schedule_source_columns_ddl


revision = "20261106_logistics_sources"
down_revision = "20261105_formation_certs"
branch_labels = None
depends_on = None


def _schemas_with_schedule_table(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'logistics_schedule' "
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
    schemas = _schemas_with_schedule_table(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(get_logistics_schedule_source_columns_ddl(schema))
    finally:
        cursor.close()


def downgrade():
    conn = op.get_bind()
    schemas = _schemas_with_schedule_table(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(
                f'''
                ALTER TABLE "{schema}".logistics_schedule
                    DROP CONSTRAINT IF EXISTS fk_logistics_schedule_gabarito;
                ALTER TABLE "{schema}".logistics_schedule
                    DROP CONSTRAINT IF EXISTS ck_logistics_schedule_source;
                ALTER TABLE "{schema}".logistics_schedule
                    DROP CONSTRAINT IF EXISTS ck_logistics_schedule_source_links;
                ALTER TABLE "{schema}".logistics_schedule
                    DROP CONSTRAINT IF EXISTS ck_logistics_schedule_evaluation_mode;
                DROP INDEX IF EXISTS "{schema}".idx_logistics_schedule_gabarito_id;
                ALTER TABLE "{schema}".logistics_schedule
                    DROP COLUMN IF EXISTS evaluation_mode;
                ALTER TABLE "{schema}".logistics_schedule
                    DROP COLUMN IF EXISTS gabarito_id;
                ALTER TABLE "{schema}".logistics_schedule
                    DROP COLUMN IF EXISTS source;
                '''
            )
            # Não recoloca NOT NULL em test_id: pode haver linhas cartão/personalizada.
    finally:
        cursor.close()
