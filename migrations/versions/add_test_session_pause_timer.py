# -*- coding: utf-8 -*-
"""Add paused_at and total_paused_seconds to test_sessions (pause timer when tab closed)

Aplica em todos os schemas onde test_sessions existe (multi-tenant: public e city_xxx).
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_test_session_pause'
down_revision = 'add_answer_sheet_sent_at'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Listar todos os schemas que têm a tabela test_sessions (public + city_xxx em multi-tenant)
    r = conn.execute(sa.text(
        "SELECT DISTINCT table_schema FROM information_schema.tables "
        "WHERE table_name = 'test_sessions'"
    ))
    schemas = [row[0] for row in r]
    for schema in schemas:
        # ADD COLUMN IF NOT EXISTS (PostgreSQL 9.5+) em cada schema (public + city_xxx)
        try:
            conn.execute(sa.text(
                f'ALTER TABLE "{schema}".test_sessions '
                'ADD COLUMN IF NOT EXISTS paused_at TIMESTAMP NULL'
            ))
            conn.execute(sa.text(
                f'ALTER TABLE "{schema}".test_sessions '
                'ADD COLUMN IF NOT EXISTS total_paused_seconds INTEGER NOT NULL DEFAULT 0'
            ))
        except Exception as e:
            # Se o schema for só-leitura ou der outro erro, continuar com os demais
            import logging
            logging.warning("Migration add_test_session_pause: schema %s: %s", schema, e)


def downgrade():
    conn = op.get_bind()
    r = conn.execute(sa.text(
        "SELECT DISTINCT table_schema FROM information_schema.tables "
        "WHERE table_name = 'test_sessions'"
    ))
    schemas = [row[0] for row in r]
    for schema in schemas:
        try:
            conn.execute(sa.text(
                f'ALTER TABLE "{schema}".test_sessions DROP COLUMN IF EXISTS total_paused_seconds'
            ))
            conn.execute(sa.text(
                f'ALTER TABLE "{schema}".test_sessions DROP COLUMN IF EXISTS paused_at'
            ))
        except Exception:
            pass
