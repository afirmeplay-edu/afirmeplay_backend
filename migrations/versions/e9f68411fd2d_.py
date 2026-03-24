"""empty message

Revision ID: e9f68411fd2d
Revises: 20260210_add_slug_to_city, dcd85bd987c7
Create Date: 2026-02-10 16:08:20.942753

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9f68411fd2d'
down_revision = ('20260210_add_slug_to_city', 'dcd85bd987c7')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
