"""empty message

Revision ID: e7b299c54c80
Revises: add_grade_id_scope_type, e65e9db85b23
Create Date: 2026-02-02 16:15:05.947655

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7b299c54c80'
down_revision = ('add_grade_id_scope_type', 'e65e9db85b23')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
