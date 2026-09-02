# -*- coding: utf-8 -*-
"""Cria cover_templates em cada schema city_* (capa de prova por avaliação).

Revision ID: 20260902_add_cover_templates
Revises: 20260716_drop_interaction_config_from_question
Create Date: 2026-09-02
"""
from alembic import op
import sqlalchemy as sa
import logging

from app.services.city_schema_service import get_cover_templates_table_ddl

log = logging.getLogger(__name__)

revision = "20260902_add_cover_templates"
down_revision = "20260716_drop_interaction_config_from_question"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name LIKE 'city_%' ORDER BY schema_name"
        )
    )
    schemas = [row[0] for row in rows]
    for schema in schemas:
        ddl = get_cover_templates_table_ddl(schema)
        for stmt in [part.strip() for part in ddl.split(";") if part.strip()]:
            conn.execute(sa.text(stmt))
        log.info("cover_templates criado/garantido em %s", schema)


def downgrade():
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name LIKE 'city_%' ORDER BY schema_name"
        )
    )
    schemas = [row[0] for row in rows]
    for schema in schemas:
        conn.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".cover_templates'))
