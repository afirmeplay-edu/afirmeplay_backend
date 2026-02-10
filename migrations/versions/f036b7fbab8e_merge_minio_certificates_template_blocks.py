"""merge_minio_certificates_template_blocks

Revision ID: f036b7fbab8e
Revises: merge_heads_2026_01_23
Create Date: 2026-01-23 13:50:57.720602

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f036b7fbab8e'
down_revision = ('add_minio_storage', 'add_certificates_tables', 'add_template_blocks')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
