"""add form_result_cache table

Revision ID: 20260204_form_cache
Revises: 
Create Date: 2026-02-04 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260204_form_cache'
down_revision = None  # Será preenchido automaticamente pelo Alembic
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela form_result_cache
    op.create_table(
        'form_result_cache',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('form_id', sa.String(), nullable=False),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('filters_hash', sa.String(64), nullable=False),
        sa.Column('filters', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('result', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('student_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_dirty', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('form_id', 'report_type', 'filters_hash', name='uq_form_report_filters')
    )
    
    # Criar índices
    op.create_index('idx_form_result_cache_form_type', 'form_result_cache', ['form_id', 'report_type'])
    op.create_index('idx_form_result_cache_dirty', 'form_result_cache', ['is_dirty'])


def downgrade():
    # Remover índices
    op.drop_index('idx_form_result_cache_dirty', table_name='form_result_cache')
    op.drop_index('idx_form_result_cache_form_type', table_name='form_result_cache')
    
    # Remover tabela
    op.drop_table('form_result_cache')
