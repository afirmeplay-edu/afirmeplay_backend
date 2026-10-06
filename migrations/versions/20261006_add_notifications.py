# -*- coding: utf-8 -*-
"""Tabelas notification e notification_recipient nos schemas city_%.

Só cria tabelas novas. Não altera tabelas existentes nem dados.

Revision ID: 20261006_notifications
Revises: 20261006_logistics_schedule
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa

from app.services.city_schema_service import get_notification_tables_ddl


revision = "20261006_notifications"
down_revision = "20261006_logistics_schedule"
branch_labels = None
depends_on = None


def _city_schemas_with_school(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'school' AND table_schema LIKE 'city_%' "
            "ORDER BY table_schema"
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
    schemas = _city_schemas_with_school(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(get_notification_tables_ddl(schema))
    finally:
        cursor.close()


def downgrade():
    conn = op.get_bind()
    schemas = _city_schemas(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(f'DROP TABLE IF EXISTS "{schema}".notification_recipient')
            cursor.execute(f'DROP TABLE IF EXISTS "{schema}".notification')
    finally:
        cursor.close()
