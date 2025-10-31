"""Merge heads before adding batch correction job

Revision ID: 6e291f89aa03
Revises: 266a3a4f7474, add_batch_correction_job
Create Date: 2025-09-22 10:12:55.878327

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6e291f89aa03'
down_revision = ('add_batch_correction_job')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
