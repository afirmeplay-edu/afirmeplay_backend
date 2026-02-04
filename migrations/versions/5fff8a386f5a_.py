"""empty message

Revision ID: 5fff8a386f5a
Revises: 20260203_fix_expected_tasks, merge_competitions_head
Create Date: 2026-02-04 16:56:33.387469

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5fff8a386f5a'
down_revision = ('20260203_fix_expected_tasks', 'merge_competitions_head')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
