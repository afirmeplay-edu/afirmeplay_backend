# -*- coding: utf-8 -*-
"""Colunas icon e icon_color em public.store_items.

Revision ID: 20260921_store_item_icon
Revises: 20260921_content_rewards
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa

revision = '20260921_store_item_icon'
down_revision = '20260921_content_rewards'
branch_labels = None
depends_on = None


def _column_exists(conn, table_name, column_name, schema='public'):
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": schema, "table": table_name, "col": column_name},
    ).scalar()
    return row is not None


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, 'store_items', 'icon'):
        op.add_column('store_items', sa.Column('icon', sa.String(128), nullable=True))
    if not _column_exists(conn, 'store_items', 'icon_color'):
        op.add_column('store_items', sa.Column('icon_color', sa.String(32), nullable=True))


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, 'store_items', 'icon_color'):
        op.drop_column('store_items', 'icon_color')
    if _column_exists(conn, 'store_items', 'icon'):
        op.drop_column('store_items', 'icon')
