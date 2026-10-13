# -*- coding: utf-8 -*-
"""Coluna anulável public.test.paired_regular_test_id.

Alinha public.test ao model Test após 20261003_paired_regular_test_id
(que só tocou schemas city_%). Só ADD COLUMN se a tabela existir e a
coluna ainda não. Sem default, sem índice único, sem preencher dados.

Revision ID: 20261003_paired_regular_test_id_public
Revises: 20261003_paired_regular_test_id
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa


revision = "20261003_paired_regular_test_id_public"
down_revision = "20261003_paired_regular_test_id"
branch_labels = None
depends_on = None


def _dbapi_cursor(conn):
    raw = conn.connection
    cursor = raw.cursor() if hasattr(raw, "cursor") else raw.dbapi_connection.cursor()
    return cursor


def _public_test_exists(conn) -> bool:
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'test' "
            "LIMIT 1"
        )
    ).fetchone()
    return bool(row)


def _public_column_exists(conn) -> bool:
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'test' "
            "AND column_name = 'paired_regular_test_id' "
            "LIMIT 1"
        )
    ).fetchone()
    return bool(row)


def upgrade():
    conn = op.get_bind()
    if not _public_test_exists(conn):
        return
    if _public_column_exists(conn):
        return
    cursor = _dbapi_cursor(conn)
    try:
        cursor.execute(
            "ALTER TABLE public.test "
            "ADD COLUMN paired_regular_test_id VARCHAR"
        )
        cursor.execute(
            "COMMENT ON COLUMN public.test.paired_regular_test_id IS "
            "'Prova regular correspondente (só em provas ADAP). NULL = sem pareamento.'"
        )
    finally:
        cursor.close()


def downgrade():
    conn = op.get_bind()
    if not _public_test_exists(conn):
        return
    if not _public_column_exists(conn):
        return
    cursor = _dbapi_cursor(conn)
    try:
        cursor.execute(
            "ALTER TABLE public.test "
            "DROP COLUMN IF EXISTS paired_regular_test_id"
        )
    finally:
        cursor.close()
