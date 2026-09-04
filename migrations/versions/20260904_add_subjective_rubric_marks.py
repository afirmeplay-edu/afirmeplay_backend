# -*- coding: utf-8 -*-
"""Marcações configuráveis da rubrica subjetiva + alarga value.

Revision ID: 20260904_subjective_rubric_marks
Revises: 20260902_add_cover_templates, 20260902_municipality_availability
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa
import logging

from app.services.city_schema_service import get_subjective_rubric_marks_upgrade_ddl

log = logging.getLogger(__name__)

revision = "20260904_subjective_rubric_marks"
down_revision = ("20260902_add_cover_templates", "20260902_municipality_availability")
branch_labels = None
depends_on = None


_SEED_MARKS_SQL = """
INSERT INTO "{schema}".subjective_rubric_marks
    (id, subjective_test_id, code, label, color, weight, sort_order)
SELECT
    md5(t.id || v.code),
    t.id,
    v.code,
    v.label,
    v.color,
    v.weight,
    v.sort_order
FROM "{schema}".subjective_tests t
CROSS JOIN (
    VALUES
        ('SIM', 'Sim', '#22c55e', 1.0::float, 0),
        ('PARCIAL', 'Parcial', '#eab308', 0.5::float, 1),
        ('NAO', 'Não', '#ef4444', 0.0::float, 2),
        ('BRANCO', 'Branco', '#94a3b8', 0.0::float, 3)
) AS v(code, label, color, weight, sort_order)
WHERE NOT EXISTS (
    SELECT 1 FROM "{schema}".subjective_rubric_marks m
    WHERE m.subjective_test_id = t.id
)
"""


def _city_schemas(conn):
    rows = conn.execute(
        sa.text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name LIKE 'city_%' ORDER BY schema_name"
        )
    )
    return [row[0] for row in rows]


def upgrade():
    conn = op.get_bind()
    schemas = _city_schemas(conn)
    for schema in schemas:
        ddl = get_subjective_rubric_marks_upgrade_ddl(schema)
        for stmt in [part.strip() for part in ddl.split(";") if part.strip()]:
            conn.execute(sa.text(stmt))
        conn.execute(sa.text(_SEED_MARKS_SQL.format(schema=schema)))
        log.info("subjective_rubric_marks criado/seed em %s", schema)


def downgrade():
    conn = op.get_bind()
    for schema in _city_schemas(conn):
        conn.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".subjective_rubric_marks'))
