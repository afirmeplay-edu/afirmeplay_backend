# -*- coding: utf-8 -*-
"""Add ideb_meta_saves table (Calculadora de Metas IDEB)

Revision ID: add_ideb_meta_saves
Revises: add_competition_templates
Create Date: 2026-02-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_ideb_meta_saves'
down_revision = 'add_competition_templates'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ideb_meta_saves',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('state_id', sa.String(length=50), nullable=False),
        sa.Column('municipality_id', sa.String(length=50), nullable=False),
        sa.Column('level', sa.String(length=100), nullable=False),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('state_id', 'municipality_id', 'level', name='uq_ideb_meta_saves_context'),
    )
    op.create_index('idx_ideb_meta_saves_context', 'ideb_meta_saves', ['state_id', 'municipality_id', 'level'])


def downgrade():
    op.drop_index('idx_ideb_meta_saves_context', table_name='ideb_meta_saves')
    op.drop_table('ideb_meta_saves')
