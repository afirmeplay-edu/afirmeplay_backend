"""Add filters and selected_classes fields to forms table

Revision ID: add_filters_selected_classes_forms
Revises: add_selected_grades_forms
Create Date: 2025-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_filters_selected_classes_forms'
down_revision = 'add_selected_grades_forms'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar coluna filters na tabela forms
    op.add_column('forms', 
        sa.Column('filters', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )
    
    # Adicionar coluna selected_classes na tabela forms
    op.add_column('forms', 
        sa.Column('selected_classes', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade():
    # Remover coluna selected_classes da tabela forms
    op.drop_column('forms', 'selected_classes')
    
    # Remover coluna filters da tabela forms
    op.drop_column('forms', 'filters')

