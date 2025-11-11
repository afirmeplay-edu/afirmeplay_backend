"""merge heads

Revision ID: 966ab4061d7b
Revises: 1a2b3c4d5e6f, 65327aea07c3, d3f4a5b6c7d8
Create Date: 2025-11-10 21:19:54.268441

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '966ab4061d7b'
down_revision = ('1a2b3c4d5e6f', '65327aea07c3', 'd3f4a5b6c7d8')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
