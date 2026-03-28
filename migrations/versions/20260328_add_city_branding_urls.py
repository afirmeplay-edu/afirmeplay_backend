# -*- coding: utf-8 -*-
"""Add municipality branding asset URLs to public.city

Logo (PNG/JPEG), letterhead raster (PNG from PDF page 1), optional letterhead PDF.
API authorization (tecadmin, admin, diretor, coordenador + city_id) is enforced in routes, not here.

Revision ID: add_city_branding_urls
Revises: 8300cf5fcc89
Create Date: 2026-03-28

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_city_branding_urls'
down_revision = '8300cf5fcc89'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'city',
        sa.Column('logo_url', sa.Text(), nullable=True),
    )
    op.add_column(
        'city',
        sa.Column('letterhead_image_url', sa.Text(), nullable=True),
    )
    op.add_column(
        'city',
        sa.Column('letterhead_pdf_url', sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column('city', 'letterhead_pdf_url')
    op.drop_column('city', 'letterhead_image_url')
    op.drop_column('city', 'logo_url')
