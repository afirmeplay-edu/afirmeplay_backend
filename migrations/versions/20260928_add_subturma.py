# -*- coding: utf-8 -*-
"""Subturma ADAP (tabela + coluna anulável em student) nos schemas city_%.

Não altera linhas existentes. student.subturma_id nasce NULL.

Revision ID: 20260928_add_subturma
Revises: 20260925_school_area_type
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

from app.services.city_schema_service import get_subturma_tables_ddl


revision = "20260928_add_subturma"
down_revision = "20260925_school_area_type"
branch_labels = None
depends_on = None


def _city_schemas_with_class_and_student(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'class' AND table_schema LIKE 'city_%' "
            "AND table_schema IN ("
            "  SELECT table_schema FROM information_schema.tables "
            "  WHERE table_name = 'student' AND table_schema LIKE 'city_%'"
            ") "
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
    schemas = _city_schemas_with_class_and_student(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(get_subturma_tables_ddl(schema))
    finally:
        cursor.close()


def downgrade():
    conn = op.get_bind()
    schemas = _city_schemas_with_class_and_student(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(
                f'DROP TRIGGER IF EXISTS trg_student_subturma_same_class '
                f'ON "{schema}".student'
            )
            cursor.execute(
                f'DROP FUNCTION IF EXISTS "{schema}".fn_student_subturma_same_class()'
            )
            cursor.execute(
                f'ALTER TABLE "{schema}".student DROP COLUMN IF EXISTS subturma_id'
            )
            cursor.execute(f'DROP TABLE IF EXISTS "{schema}".subturma')
    finally:
        cursor.close()
