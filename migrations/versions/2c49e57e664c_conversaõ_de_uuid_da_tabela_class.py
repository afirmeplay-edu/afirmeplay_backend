"""conversaõ de uuid da tabela class

Revision ID: 2c49e57e664c
Revises: 507b7f6fa3d9, convert_class_to_uuid
Create Date: 2026-01-07 11:44:20.457600

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2c49e57e664c'
down_revision = ('507b7f6fa3d9', 'convert_class_to_uuid')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
