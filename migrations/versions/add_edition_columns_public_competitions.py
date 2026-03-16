# -*- coding: utf-8 -*-
"""Adiciona edition_number e edition_series em public.competitions (idempotente).

Corrige o erro ao excluir avaliação:
  column competitions.edition_number does not exist

A tabela competitions fica no schema public.

Revision ID: add_edition_columns_public
Revises: ensure_competitions_public
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_edition_columns_public'
down_revision = 'ensure_competitions_public'
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

    if not _table_exists(connection, 'public', 'competitions'):
        return

    if not _column_exists(connection, 'public', 'competitions', 'edition_number'):
        op.execute(sa.text(
            "ALTER TABLE public.competitions ADD COLUMN edition_number INTEGER NULL"
        ))
    if not _column_exists(connection, 'public', 'competitions', 'edition_series'):
        op.execute(sa.text(
            "ALTER TABLE public.competitions ADD COLUMN edition_series VARCHAR NULL"
        ))


def downgrade():
    # Opcional: remover colunas. Descomente se quiser rollback.
    # connection = op.get_bind()
    # if _column_exists(connection, 'public', 'competitions', 'edition_series'):
    #     op.execute(sa.text("ALTER TABLE public.competitions DROP COLUMN edition_series"))
    # if _column_exists(connection, 'public', 'competitions', 'edition_number'):
    #     op.execute(sa.text("ALTER TABLE public.competitions DROP COLUMN edition_number"))
    pass
