"""Add form_type to physical_test_forms

Revision ID: add_form_type_physical
Revises: 0fe0422f58b0
Create Date: 2025-01-18 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_form_type_physical'
down_revision = '0fe0422f58b0'
branch_labels = None
depends_on = None


def upgrade():
    """Add form_type column to physical_test_forms"""
    with op.batch_alter_table('physical_test_forms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('form_type', sa.String(50), nullable=True, default='institutional'))


def downgrade():
    """Remove form_type column from physical_test_forms"""
    with op.batch_alter_table('physical_test_forms', schema=None) as batch_op:
        batch_op.drop_column('form_type')
