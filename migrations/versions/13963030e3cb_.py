"""empty message

Revision ID: 13963030e3cb
Revises: add_correction_fields_physical, add_student_test_olimpics, f036b7fbab8e
Create Date: 2026-01-27 18:47:38.130930

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '13963030e3cb'
down_revision = ('add_correction_fields_physical', 'add_student_test_olimpics', 'f036b7fbab8e')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
