"""add user address field

Revision ID: d3f4a5b6c7d8
Revises: c91b2d3e4f50
Create Date: 2025-11-07 00:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3f4a5b6c7d8'
down_revision = 'c91b2d3e4f50'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('address', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('address')

