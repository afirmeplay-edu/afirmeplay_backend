"""Add grade_id and scope_type fields to answer_sheet_gabaritos

Adiciona rastreamento de escopo (turma/série/escola) e vinculação com série.

Revision ID: add_grade_id_scope_type
Revises: add_template_blocks
Create Date: 2026-02-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_grade_id_scope_type'
down_revision = 'add_template_blocks'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar grade_id (vinculação com série)
    op.add_column('answer_sheet_gabaritos',
        sa.Column('grade_id', UUID(as_uuid=True), nullable=True)
    )
    
    # Adicionar constraint de foreign key
    op.create_foreign_key(
        'fk_answer_sheet_gabaritos_grade_id',
        'answer_sheet_gabaritos', 'grade',
        ['grade_id'], ['id']
    )
    
    # Adicionar scope_type (class | grade | school | city)
    op.add_column('answer_sheet_gabaritos',
        sa.Column('scope_type', sa.String(50), nullable=False, server_default='class')
    )


def downgrade():
    # Remover constraint de foreign key
    op.drop_constraint('fk_answer_sheet_gabaritos_grade_id', 'answer_sheet_gabaritos', type_='foreignkey')
    
    # Remover colunas
    op.drop_column('answer_sheet_gabaritos', 'grade_id')
    op.drop_column('answer_sheet_gabaritos', 'scope_type')
