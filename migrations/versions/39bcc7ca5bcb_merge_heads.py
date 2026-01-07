"""merge heads

Revision ID: 39bcc7ca5bcb
Revises: add_student_password_log, migrate_school_course_data
Create Date: 2025-11-04 14:15:02.181102

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '39bcc7ca5bcb'
down_revision = ('add_student_password_log', 'migrate_school_course_data')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
