"""add user profile fields

Revision ID: c91b2d3e4f50
Revises: f8a4d5c6a8d9
Create Date: 2025-11-07 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c91b2d3e4f50'
down_revision = 'f8a4d5c6a8d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('birth_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('nationality', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('gender', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('traits', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('avatar_config', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('avatar_config')
        batch_op.drop_column('traits')
        batch_op.drop_column('gender')
        batch_op.drop_column('phone')
        batch_op.drop_column('nationality')
        batch_op.drop_column('birth_date')

