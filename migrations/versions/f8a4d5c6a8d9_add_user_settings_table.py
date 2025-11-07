"""add user settings table

Revision ID: f8a4d5c6a8d9
Revises: 0fe0422f58b0
Create Date: 2025-11-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8a4d5c6a8d9'
down_revision = '0fe0422f58b0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_settings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('theme', sa.String(length=50), nullable=True),
        sa.Column('font_family', sa.String(length=100), nullable=True),
        sa.Column('font_size', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_user_settings_user_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_user_settings_user_id')
    )


def downgrade():
    op.drop_table('user_settings')

