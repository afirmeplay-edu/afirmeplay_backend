# -*- coding: utf-8 -*-
"""Merge head (coins/grade) com add_competitions_tables

Revision ID: merge_competitions_head
Revises: f1e2d3c4b5a6, add_competitions_tables
Create Date: 2026-02-03

Assim o upgrade aplica add_competitions_tables quando o banco estava só em f1e2d3c4b5a6.
"""
from alembic import op
import sqlalchemy as sa

revision = 'merge_competitions_head'
down_revision = ('f1e2d3c4b5a6', 'add_competitions_tables')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
