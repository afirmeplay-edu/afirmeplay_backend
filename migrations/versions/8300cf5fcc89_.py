"""empty message

Revision ID: 8300cf5fcc89
Revises: add_edition_columns_public, dd68ebe60410
Create Date: 2026-03-16 16:25:26.162982

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8300cf5fcc89'
down_revision = ('add_edition_columns_public', 'dd68ebe60410')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
