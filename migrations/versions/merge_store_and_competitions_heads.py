# -*- coding: utf-8 -*-
"""Merge heads: add_store_tables e merge_pause_competitions (competições + pause timer)

Revision ID: merge_store_competitions
Revises: add_store_tables, merge_pause_competitions
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa

revision = 'merge_store_competitions'
down_revision = ('add_store_tables', 'merge_pause_competitions')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
