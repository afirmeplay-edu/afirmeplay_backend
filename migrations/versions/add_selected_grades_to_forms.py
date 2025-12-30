"""Add selected_grades field to forms table

Revision ID: add_selected_grades_forms
Revises: socioeconomic_forms_001
Create Date: 2025-12-29 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_selected_grades_forms'
down_revision = 'socioeconomic_forms_001'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar coluna selected_grades na tabela forms
    op.add_column('forms', 
        sa.Column('selected_grades', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade():
    # Remover coluna selected_grades da tabela forms
    op.drop_column('forms', 'selected_grades')

