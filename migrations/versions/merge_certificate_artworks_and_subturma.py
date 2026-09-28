# -*- coding: utf-8 -*-
"""Merge heads: certificate_artworks e subturma

Revision ID: merge_certificate_artworks_subturma
Revises: 20260925_add_certificate_artworks, 20260928_add_subturma
Create Date: 2026-09-28

"""
from alembic import op
import sqlalchemy as sa


revision = "merge_certificate_artworks_subturma"
down_revision = ("20260925_add_certificate_artworks", "20260928_add_subturma")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
