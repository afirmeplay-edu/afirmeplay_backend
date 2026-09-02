# -*- coding: utf-8 -*-
"""Disponibilidade municipal em test e answer_sheet_gabaritos.

Revision ID: 20260902_municipality_availability
Revises: 20260716_drop_interaction_config_from_question
Create Date: 2026-09-02

Adiciona available_to_municipality e available_from em todos os schemas
que tenham as tabelas (public + city_xxx). Default True preserva o legado.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260902_municipality_availability"
down_revision = "20260716_drop_interaction_config_from_question"
branch_labels = None
depends_on = None


_STMTS = (
    (
        "test",
        [
            "ADD COLUMN IF NOT EXISTS available_to_municipality BOOLEAN NOT NULL DEFAULT true",
            "ADD COLUMN IF NOT EXISTS available_from TIMESTAMPTZ",
        ],
    ),
    (
        "answer_sheet_gabaritos",
        [
            "ADD COLUMN IF NOT EXISTS available_to_municipality BOOLEAN NOT NULL DEFAULT true",
            "ADD COLUMN IF NOT EXISTS available_from TIMESTAMPTZ",
        ],
    ),
)


def _schemas_with_table(conn, table_name):
    rows = conn.execute(
        sa.text(
            "SELECT DISTINCT table_schema FROM information_schema.tables "
            "WHERE table_name = :table_name"
        ),
        {"table_name": table_name},
    )
    return [row[0] for row in rows]


def upgrade():
    conn = op.get_bind()
    for table_name, alters in _STMTS:
        for schema in _schemas_with_table(conn, table_name):
            for alter in alters:
                conn.execute(
                    sa.text(f'ALTER TABLE "{schema}".{table_name} {alter}')
                )


def downgrade():
    conn = op.get_bind()
    drops = (
        ("test", ["available_from", "available_to_municipality"]),
        ("answer_sheet_gabaritos", ["available_from", "available_to_municipality"]),
    )
    for table_name, columns in drops:
        for schema in _schemas_with_table(conn, table_name):
            for column in columns:
                conn.execute(
                    sa.text(
                        f'ALTER TABLE "{schema}".{table_name} '
                        f'DROP COLUMN IF EXISTS {column}'
                    )
                )
