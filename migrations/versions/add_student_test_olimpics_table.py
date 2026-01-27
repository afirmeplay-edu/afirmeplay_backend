"""Add student_test_olimpics table

Revision ID: add_student_test_olimpics
Revises: add_certificates_tables
Create Date: 2025-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_student_test_olimpics'
down_revision = 'add_certificates_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'student_test_olimpics',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('test_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('application', sa.Text(), nullable=False),
        sa.Column('expiration', sa.Text(), nullable=False),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['student.id'], ),
        sa.ForeignKeyConstraint(['test_id'], ['test.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'test_id', name='uq_student_test_olimpics_student_test')
    )


def downgrade():
    op.drop_table('student_test_olimpics')
