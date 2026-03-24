"""merge test sessions e answer sheet

Revision ID: dd68ebe60410
Revises: add_answer_sheet_gen_jobs, add_test_sessions_public
Create Date: 2026-03-11 10:25:12.094344

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd68ebe60410'
down_revision = ('add_answer_sheet_gen_jobs', 'add_test_sessions_public')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
