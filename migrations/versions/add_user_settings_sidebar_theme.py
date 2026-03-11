# -*- coding: utf-8 -*-
"""Add sidebar_theme_id, frame_id, stamp_id to user_settings

Revision ID: add_user_settings_sidebar
Revises: merge_store_competitions
Create Date: 2026-03-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'add_user_settings_sidebar'
down_revision = 'merge_store_competitions'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    insp = inspect(conn)
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, 'user_settings', 'sidebar_theme_id'):
        op.add_column('user_settings', sa.Column('sidebar_theme_id', sa.String(128), nullable=True))
    if not _column_exists(conn, 'user_settings', 'frame_id'):
        op.add_column('user_settings', sa.Column('frame_id', sa.String(128), nullable=True))
    if not _column_exists(conn, 'user_settings', 'stamp_id'):
        op.add_column('user_settings', sa.Column('stamp_id', sa.String(128), nullable=True))


def downgrade():
    op.drop_column('user_settings', 'stamp_id')
    op.drop_column('user_settings', 'frame_id')
    op.drop_column('user_settings', 'sidebar_theme_id')
