# -*- coding: utf-8 -*-
"""Tabelas logistics_schedule e logistics_schedule_item nos schemas city_%.

Só cria tabelas novas. Não altera tabelas existentes nem dados.
Também une as duas heads atuais (result_snapshots e paired_regular_test_id_public).

Revision ID: 20261006_logistics_schedule
Revises: 20261002_result_snapshots, 20261003_paired_regular_test_id_public
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa

from app.services.city_schema_service import get_logistics_schedule_tables_ddl


revision = "20261006_logistics_schedule"
down_revision = ("20261002_result_snapshots", "20261003_paired_regular_test_id_public")
branch_labels = None
depends_on = None


def _city_schemas_with_test_and_class(conn):
    rows = conn.execute(
        sa.text(
            "SELECT t.table_schema FROM information_schema.tables t "
            "WHERE t.table_name = 'test' AND t.table_schema LIKE 'city_%' "
            "AND EXISTS ("
            "  SELECT 1 FROM information_schema.tables c "
            "  WHERE c.table_schema = t.table_schema AND c.table_name = 'class'"
            ") "
            "ORDER BY t.table_schema"
        )
    )
    return [row[0] for row in rows]


def _city_schemas(conn):
    rows = conn.execute(
        sa.text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name LIKE 'city_%' ORDER BY schema_name"
        )
    )
    return [row[0] for row in rows]


def _dbapi_cursor(conn):
    raw = conn.connection
    cursor = raw.cursor() if hasattr(raw, "cursor") else raw.dbapi_connection.cursor()
    return cursor


def upgrade():
    conn = op.get_bind()
    schemas = _city_schemas_with_test_and_class(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(get_logistics_schedule_tables_ddl(schema))
    finally:
        cursor.close()


def downgrade():
    conn = op.get_bind()
    schemas = _city_schemas(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(f'DROP TABLE IF EXISTS "{schema}".logistics_schedule_item')
            cursor.execute(f'DROP TABLE IF EXISTS "{schema}".logistics_schedule')
    finally:
        cursor.close()
