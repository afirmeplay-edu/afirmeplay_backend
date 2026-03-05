# -*- coding: utf-8 -*-
"""Merge heads: add_test_session_pause e recreate_competitions_public

Revision ID: merge_pause_competitions
Revises: add_test_session_pause, recreate_competitions_public
Create Date: 2026-03-05

"""
from alembic import op


revision = 'merge_pause_competitions'
down_revision = ('add_test_session_pause', 'recreate_competitions_public')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
