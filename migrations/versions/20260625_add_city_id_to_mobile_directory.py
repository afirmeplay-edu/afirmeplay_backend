# -*- coding: utf-8 -*-
"""Add city_id to mobile_city_directory

Revision ID: 20260625_add_city_id_to_mobile_directory
Revises: add_afirme_ler_tables
Create Date: 2026-06-25

Adiciona coluna city_id (FK opcional) para referenciar municípios da VPS central.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260625_add_city_id_to_mobile_directory"
down_revision = "add_afirme_ler_tables"
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar coluna city_id (nullable para municípios em VPS dedicada)
    op.add_column(
        'mobile_city_directory',
        sa.Column('city_id', sa.String(36), nullable=True),
        schema='public'
    )
    
    # Criar índice (não unique pois pode ser NULL para VPS dedicadas)
    op.create_index(
        'idx_mobile_city_directory_city_id',
        'mobile_city_directory',
        ['city_id'],
        schema='public'
    )


def downgrade():
    op.drop_index(
        'idx_mobile_city_directory_city_id',
        table_name='mobile_city_directory',
        schema='public'
    )
    
    op.drop_column(
        'mobile_city_directory',
        'city_id',
        schema='public'
    )
