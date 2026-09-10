# -*- coding: utf-8 -*-
"""Grupos de critérios da rubrica subjetiva + vínculo questão↔grupo.

Revision ID: 20260909_subjective_rubric_groups
Revises: 20260904_subjective_rubric_marks
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa
import logging

from app.services.city_schema_service import get_subjective_rubric_groups_upgrade_ddl

log = logging.getLogger(__name__)

revision = "20260909_subjective_rubric_groups"
down_revision = "20260904_subjective_rubric_marks"
branch_labels = None
depends_on = None


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
    for schema in _city_schemas(conn):
        ddl = get_subjective_rubric_groups_upgrade_ddl(schema)
        # Split carefully: DO $$ ... END $$; blocks contain semicolons
        parts = []
        buffer = []
        in_do = False
        for line in ddl.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("DO $$"):
                in_do = True
            buffer.append(line)
            if in_do:
                if stripped.upper().startswith("END $$"):
                    in_do = False
                    parts.append("\n".join(buffer).strip())
                    buffer = []
            elif stripped.endswith(";"):
                parts.append("\n".join(buffer).strip().rstrip(";"))
                buffer = []
        if buffer:
            leftover = "\n".join(buffer).strip().rstrip(";")
            if leftover:
                parts.append(leftover)
        for stmt in parts:
            if stmt:
                conn.execute(sa.text(stmt))
        log.info("subjective_rubric_groups aplicado em %s", schema)


def downgrade():
    conn = op.get_bind()
    for schema in _city_schemas(conn):
        conn.execute(sa.text(
            f'ALTER TABLE "{schema}".subjective_questions DROP CONSTRAINT IF EXISTS fk_subjective_questions_rubric_group'
        ))
        conn.execute(sa.text(
            f'ALTER TABLE "{schema}".subjective_rubric_marks DROP CONSTRAINT IF EXISTS fk_subjective_rubric_marks_group'
        ))
        conn.execute(sa.text(
            f'ALTER TABLE "{schema}".subjective_questions DROP COLUMN IF EXISTS rubric_group_id'
        ))
        conn.execute(sa.text(
            f'ALTER TABLE "{schema}".subjective_rubric_marks DROP COLUMN IF EXISTS rubric_group_id'
        ))
        conn.execute(sa.text(
            f'DROP TABLE IF EXISTS "{schema}".subjective_rubric_groups'
        ))
