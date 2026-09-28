# -*- coding: utf-8 -*-
"""Tabelas content_sessions e content_rewards (recompensas Jogos / Play TV).

Revision ID: 20260921_content_rewards
Revises: 20260909_subjective_rubric_groups
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa
import logging

from app.services.city_schema_service import get_content_rewards_tables_ddl

log = logging.getLogger(__name__)

revision = "20260921_content_rewards"
down_revision = "20260909_subjective_rubric_groups"
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
        ddl = get_content_rewards_tables_ddl(schema)
        for stmt in ddl.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(sa.text(stmt))
        log.info("content_rewards aplicado em %s", schema)


def downgrade():
    conn = op.get_bind()
    for schema in _city_schemas(conn):
        conn.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".content_rewards'))
        conn.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".content_sessions'))
        log.info("content_rewards removido de %s", schema)
