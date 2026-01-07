"""Add answer_sheet_sent_at to physical_test_forms

Revision ID: add_answer_sheet_sent_at
Revises: add_form_type_physical
Create Date: 2025-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_answer_sheet_sent_at'
down_revision = 'b813cdb16b4d'  # Merge head que inclui add_form_type_physical
branch_labels = None
depends_on = None


def upgrade():
    """Add answer_sheet_sent_at column to physical_test_forms"""
    with op.batch_alter_table('physical_test_forms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('answer_sheet_sent_at', sa.DateTime(), nullable=True))


def downgrade():
    """Remove answer_sheet_sent_at column from physical_test_forms"""
    with op.batch_alter_table('physical_test_forms', schema=None) as batch_op:
        batch_op.drop_column('answer_sheet_sent_at')
