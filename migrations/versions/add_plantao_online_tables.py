"""Add plantao_online and plantao_schools tables

Revision ID: add_plantao_online_tables
Revises: f036b7fbab8e
Create Date: 2025-01-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_plantao_online_tables'
down_revision = 'f036b7fbab8e'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela plantao_online
    op.create_table('plantao_online',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('link', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('grade_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subject_id', sa.String(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['grade_id'], ['grade.id'], ),
        sa.ForeignKeyConstraint(['subject_id'], ['subject.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Criar índices para plantao_online
    op.create_index(op.f('ix_plantao_online_grade_id'), 'plantao_online', ['grade_id'], unique=False)
    op.create_index(op.f('ix_plantao_online_subject_id'), 'plantao_online', ['subject_id'], unique=False)
    op.create_index(op.f('ix_plantao_online_created_by'), 'plantao_online', ['created_by'], unique=False)
    
    # Criar tabela plantao_schools
    op.create_table('plantao_schools',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('plantao_id', sa.String(), nullable=False),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['plantao_id'], ['plantao_online.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['school.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plantao_id', 'school_id', name='uq_plantao_school')
    )
    
    # Criar índices para plantao_schools
    op.create_index(op.f('ix_plantao_schools_plantao_id'), 'plantao_schools', ['plantao_id'], unique=False)
    op.create_index(op.f('ix_plantao_schools_school_id'), 'plantao_schools', ['school_id'], unique=False)


def downgrade():
    # Remover índices
    op.drop_index(op.f('ix_plantao_schools_school_id'), table_name='plantao_schools')
    op.drop_index(op.f('ix_plantao_schools_plantao_id'), table_name='plantao_schools')
    op.drop_index(op.f('ix_plantao_online_created_by'), table_name='plantao_online')
    op.drop_index(op.f('ix_plantao_online_subject_id'), table_name='plantao_online')
    op.drop_index(op.f('ix_plantao_online_grade_id'), table_name='plantao_online')
    
    # Remover tabelas
    op.drop_table('plantao_schools')
    op.drop_table('plantao_online')
