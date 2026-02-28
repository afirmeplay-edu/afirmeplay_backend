# -*- coding: utf-8 -*-
"""Garante tabelas de competições no schema public e colunas edition em public.competitions.

Competições de escopo individual/estado/global são gravadas em public.
Esta migration garante que public tenha as tabelas e as colunas edition_number, edition_series.

Revision ID: ensure_competitions_public
Revises: 65327aea07c3
Create Date: 2026-02-27

"""
from alembic import op
import sqlalchemy as sa

revision = 'ensure_competitions_public'
down_revision = 'add_ideb_meta_saves'
branch_labels = None
depends_on = None


def _table_exists(connection, schema, table_name):
    r = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name"
        ),
        {"schema": schema, "name": table_name},
    )
    return r.scalar() is not None


def _column_exists(connection, schema, table_name, column_name):
    r = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :tname AND column_name = :cname"
        ),
        {"schema": schema, "tname": table_name, "cname": column_name},
    )
    return r.scalar() is not None


def upgrade():
    connection = op.get_bind()

    # Garantir colunas edition em public.competitions (idempotente)
    if _table_exists(connection, 'public', 'competitions'):
        if not _column_exists(connection, 'public', 'competitions', 'edition_number'):
            op.execute(sa.text(
                "ALTER TABLE public.competitions ADD COLUMN edition_number INTEGER NULL"
            ))
        if not _column_exists(connection, 'public', 'competitions', 'edition_series'):
            op.execute(sa.text(
                "ALTER TABLE public.competitions ADD COLUMN edition_series VARCHAR NULL"
            ))


def downgrade():
    # Não removemos colunas para evitar perda de dados; reverter manualmente se necessário
    pass
