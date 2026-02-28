# -*- coding: utf-8 -*-
"""Add ideb_meta_saves table (Calculadora de Metas IDEB)

Usa city_id (município do sistema) + level para contexto.
Revision ID: add_ideb_meta_saves
Revises: skill_grade_n_n
Create Date: 2026-02-26

Idempotente: cria tabela apenas se não existir.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_ideb_meta_saves'
down_revision = 'skill_grade_n_n'
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


def upgrade():
    conn = op.get_bind()
    if _table_exists(conn, 'public', 'ideb_meta_saves'):
        return
    # Tabela no schema public (compartilhada; city_id referencia public.city)
    op.create_table(
        'ideb_meta_saves',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('city_id', sa.String(), nullable=False),
        sa.Column('level', sa.String(length=100), nullable=False),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['city_id'],
            ['city.id'],
            ondelete='CASCADE',
        ),
        sa.UniqueConstraint('city_id', 'level', name='uq_ideb_meta_saves_context'),
        schema='public',
    )
    op.create_index('idx_ideb_meta_saves_context', 'ideb_meta_saves', ['city_id', 'level'], schema='public')


def downgrade():
    conn = op.get_bind()
    if not _table_exists(conn, 'public', 'ideb_meta_saves'):
        return
    op.drop_index('idx_ideb_meta_saves_context', table_name='ideb_meta_saves', schema='public')
    op.drop_table('ideb_meta_saves', schema='public')
