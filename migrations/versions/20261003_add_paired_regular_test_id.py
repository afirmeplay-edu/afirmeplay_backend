# -*- coding: utf-8 -*-
"""Coluna anulável test.paired_regular_test_id nos schemas city_%.

Só adiciona a coluna. Não preenche, não cria índice único, não altera dados.

Revision ID: 20261003_paired_regular_test_id
Revises: merge_certificate_artworks_subturma
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa

from app.services.city_schema_service import get_paired_regular_test_id_ddl


revision = "20261003_paired_regular_test_id"
down_revision = "merge_certificate_artworks_subturma"
branch_labels = None
depends_on = None


def _city_schemas_with_test(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'test' AND table_schema LIKE 'city_%' "
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
    schemas = _city_schemas_with_test(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(get_paired_regular_test_id_ddl(schema))
    finally:
        cursor.close()


def downgrade():
    conn = op.get_bind()
    schemas = _city_schemas_with_test(conn)
    cursor = _dbapi_cursor(conn)
    try:
        for schema in schemas:
            cursor.execute(
                f'ALTER TABLE "{schema}".test '
                f"DROP COLUMN IF EXISTS paired_regular_test_id"
            )
    finally:
        cursor.close()
