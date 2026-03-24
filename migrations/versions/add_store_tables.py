# -*- coding: utf-8 -*-
"""Add store_items and student_purchases tables (Loja com afirmecoins)

Revision ID: add_store_tables
Revises: add_ideb_meta_saves
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_store_tables'
down_revision = 'add_ideb_meta_saves'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'store_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(64), nullable=False),
        sa.Column('reward_type', sa.String(64), nullable=False),
        sa.Column('reward_data', sa.Text(), nullable=True),
        sa.Column('is_physical', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('scope_type', sa.String(32), server_default='system', nullable=False),
        sa.Column('scope_filter', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # student_id sem FK: student vive nos schemas por cidade (city_xxx), não em public.
    # Em runtime, student_purchases pode estar em public ou em city_xxx (ver city_schema_service).
    op.create_table(
        'student_purchases',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('store_item_id', sa.String(), nullable=False),
        sa.Column('price_paid', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['store_item_id'], ['store_items.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_student_purchases_student_id', 'student_purchases', ['student_id'])
    op.create_index('idx_student_purchases_store_item_id', 'student_purchases', ['store_item_id'])
    op.create_index('idx_student_purchases_created_at', 'student_purchases', ['created_at'])


def downgrade():
    op.drop_index('idx_student_purchases_created_at', table_name='student_purchases')
    op.drop_index('idx_student_purchases_store_item_id', table_name='student_purchases')
    op.drop_index('idx_student_purchases_student_id', table_name='student_purchases')
    op.drop_table('student_purchases')
    op.drop_table('store_items')
