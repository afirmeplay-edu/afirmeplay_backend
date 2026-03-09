# -*- coding: utf-8 -*-
"""Add sidebar_theme_id, frame_id, stamp_id to user_settings

Revision ID: add_user_settings_sidebar
Revises: merge_store_competitions
Create Date: 2026-03-09

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_user_settings_sidebar'
down_revision = 'merge_store_competitions'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user_settings', sa.Column('sidebar_theme_id', sa.String(128), nullable=True))
    op.add_column('user_settings', sa.Column('frame_id', sa.String(128), nullable=True))
    op.add_column('user_settings', sa.Column('stamp_id', sa.String(128), nullable=True))


def downgrade():
    op.drop_column('user_settings', 'stamp_id')
    op.drop_column('user_settings', 'frame_id')
    op.drop_column('user_settings', 'sidebar_theme_id')
