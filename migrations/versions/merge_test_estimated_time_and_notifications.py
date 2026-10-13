# -*- coding: utf-8 -*-
"""Merge heads: test_estimated_time e notifications

Revision ID: merge_estimated_time_notifications
Revises: 20261006_test_estimated_time, 20261006_notifications
Create Date: 2026-10-06

"""
from alembic import op
import sqlalchemy as sa


revision = "merge_estimated_time_notifications"
down_revision = ("20261006_test_estimated_time", "20261006_notifications")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
