# -*- coding: utf-8 -*-
"""Coluna subturmas na prova subjetiva (city_% ).

Ids de subturma ADAP no escopo. A turma regular continua em classes.

Revision ID: 20261022_subjective_subturmas
Revises: 20261013_form_print_package
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa
import logging

from app.services.city_schema_service import get_subjective_subturmas_upgrade_ddl

log = logging.getLogger(__name__)

revision = "20261022_subjective_subturmas"
down_revision = "20261013_form_print_package"
branch_labels = None
depends_on = None


def _city_schemas(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'subjective_tests' AND table_schema LIKE 'city_%' "
            "ORDER BY table_schema"
        )
    )
    return [row[0] for row in rows]


def upgrade():
    conn = op.get_bind()
    for schema in _city_schemas(conn):
        for stmt in get_subjective_subturmas_upgrade_ddl(schema).split(";"):
            sql = stmt.strip()
            if sql:
                conn.execute(sa.text(sql))
        log.info("subjective_tests.subturmas aplicado em %s", schema)


def downgrade():
    conn = op.get_bind()
    for schema in _city_schemas(conn):
        conn.execute(sa.text(
            f'ALTER TABLE "{schema}".subjective_tests DROP COLUMN IF EXISTS subturmas'
        ))
