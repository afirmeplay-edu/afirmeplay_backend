"""Add template_base_image field to answer_sheet_gabaritos

Revision ID: add_template_base_image
Revises: 7dc23446799f
Create Date: 2026-01-14 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_template_base_image'
down_revision = '7dc23446799f'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar coluna template_base_image (LargeBinary) na tabela answer_sheet_gabaritos
    op.add_column('answer_sheet_gabaritos',
        sa.Column('template_base_image', sa.LargeBinary(), nullable=True)
    )


def downgrade():
    # Remover coluna template_base_image
    op.drop_column('answer_sheet_gabaritos', 'template_base_image')
