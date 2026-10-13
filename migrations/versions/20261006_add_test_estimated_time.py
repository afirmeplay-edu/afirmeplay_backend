# -*- coding: utf-8 -*-
"""Coluna test.estimated_time (minutos) nos schemas city_% e public.test.

Preenche provas existentes pela convenção de série:
  1º e 2º anos → 90 min (1h30)
  demais (3º–9º, EM, sem série) → 150 min (2h30)

NÃO executar automaticamente: o supervisor aplica esta revisão após aprovação.

Revision ID: 20261006_test_estimated_time
Revises: 20261003_paired_regular_test_id_public
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa

from app.services.city_schema_service import get_estimated_time_column_ddl


revision = "20261006_test_estimated_time"
down_revision = "20261003_paired_regular_test_id_public"
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


def _table_exists(conn, schema: str) -> bool:
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = 'test' "
            "LIMIT 1"
        ),
        {"schema": schema},
    ).fetchone()
    return bool(row)


def _column_exists(conn, schema: str) -> bool:
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'test' "
            "AND column_name = 'estimated_time' "
            "LIMIT 1"
        ),
        {"schema": schema},
    ).fetchone()
    return bool(row)


def _fill_estimated_time_sql(schema: str) -> str:
    if schema != "public" and (
        not schema.replace("_", "").isalnum() or not schema.startswith("city_")
    ):
        raise ValueError(f"Nome de schema inválido: {schema}")
    return f"""
UPDATE "{schema}".test AS t
SET estimated_time = CASE
    WHEN g.name IS NULL THEN 150
    WHEN g.name ~* 'm[eé]dio' THEN 150
    WHEN g.name ~* '(^|[^0-9])1[[:space:]]*[ºo°]?[[:space:]]*(ano|s[eé]rie)' THEN 90
    WHEN g.name ~* '(^|[^0-9])2[[:space:]]*[ºo°]?[[:space:]]*(ano|s[eé]rie)' THEN 90
    WHEN g.name ~* 'infantil|grupo' THEN 90
    ELSE 150
END
FROM public.grade AS g
WHERE t.grade_id = g.id
  AND t.estimated_time IS NULL;

UPDATE "{schema}".test
SET estimated_time = 150
WHERE estimated_time IS NULL;
"""


def upgrade():
    conn = op.get_bind()
    cursor = _dbapi_cursor(conn)
    try:
        for schema in _city_schemas_with_test(conn):
            cursor.execute(get_estimated_time_column_ddl(schema))
            cursor.execute(_fill_estimated_time_sql(schema))

        if _table_exists(conn, "public") and not _column_exists(conn, "public"):
            cursor.execute(
                "ALTER TABLE public.test ADD COLUMN estimated_time INTEGER"
            )
            cursor.execute(
                "COMMENT ON COLUMN public.test.estimated_time IS "
                "'Tempo estimado de aplicação em minutos (1º-2º anos: 90; 3º-9º: 150).'"
            )
        if _table_exists(conn, "public"):
            cursor.execute(_fill_estimated_time_sql("public"))
    finally:
        cursor.close()


def downgrade():
    conn = op.get_bind()
    cursor = _dbapi_cursor(conn)
    try:
        for schema in _city_schemas_with_test(conn):
            cursor.execute(
                f'ALTER TABLE "{schema}".test DROP COLUMN IF EXISTS estimated_time'
            )
        if _table_exists(conn, "public") and _column_exists(conn, "public"):
            cursor.execute("ALTER TABLE public.test DROP COLUMN IF EXISTS estimated_time")
    finally:
        cursor.close()
