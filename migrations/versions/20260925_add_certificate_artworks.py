# -*- coding: utf-8 -*-
"""Cria certificate_artworks em cada schema city_* (upload de arte de certificado).

Revision ID: 20260925_add_certificate_artworks
Revises: 20260921_store_item_requirement
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa
import logging

from app.services.city_schema_service import get_certificate_artworks_table_ddl

log = logging.getLogger(__name__)

revision = "20260925_add_certificate_artworks"
down_revision = "20260921_store_item_requirement"
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
        ddl = get_certificate_artworks_table_ddl(schema)
        for stmt in [part.strip() for part in ddl.split(";") if part.strip()]:
            conn.execute(sa.text(stmt))
        log.info("certificate_artworks criado/garantido em %s", schema)


def downgrade():
    conn = op.get_bind()
    for schema in _city_schemas(conn):
        conn.execute(sa.text(
            f'DROP INDEX IF EXISTS "{schema}".idx_certificate_artworks_evaluation_status'
        ))
        conn.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".certificate_artworks'))
        log.info("certificate_artworks removido de %s", schema)
