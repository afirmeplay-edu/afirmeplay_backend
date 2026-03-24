# -*- coding: utf-8 -*-
"""Merge heads: add_user_settings_sidebar e drop_competition_fk_tenant

Revision ID: merge_sidebar_drop_fk
Revises: add_user_settings_sidebar, drop_competition_fk_tenant
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa

revision = 'merge_sidebar_drop_fk'
down_revision = ('add_user_settings_sidebar', 'drop_competition_fk_tenant')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
