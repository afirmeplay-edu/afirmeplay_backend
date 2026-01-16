"""Add coordinates field to answer_sheet_gabaritos

Revision ID: add_coords_answer_sheet
Revises: ccd58942d465
Create Date: 2026-01-14 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_coords_answer_sheet'
down_revision = 'ccd58942d465'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar coluna coordinates (JSON) na tabela answer_sheet_gabaritos
    op.add_column('answer_sheet_gabaritos',
        sa.Column('coordinates', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade():
    # Remover coluna coordinates
    op.drop_column('answer_sheet_gabaritos', 'coordinates')
