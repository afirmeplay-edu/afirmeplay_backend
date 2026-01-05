"""Add competitions, competition_enrollments and competition_results tables

Revision ID: add_competitions_tables
Revises: 7151d9971a90
Create Date: 2025-01-XX 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_competitions_tables'
down_revision = '7151d9971a90'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela competitions
    op.create_table('competitions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('instrucoes', sa.String(length=500), nullable=True),
        
        # Campos específicos de competição
        sa.Column('recompensas', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('modo_selecao', sa.String(length=20), server_default='manual', nullable=True),
        sa.Column('icone', sa.String(length=100), nullable=True),
        sa.Column('cor', sa.String(length=20), nullable=True),
        sa.Column('dificuldade', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('participantes_atual', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_moedas_distribuidas', sa.Integer(), server_default='0', nullable=True),
        
        # Campos herdados de Test
        sa.Column('type', sa.String(), nullable=True),
        sa.Column('max_score', sa.Float(), nullable=True),
        sa.Column('time_limit', sa.TIMESTAMP(), nullable=True),
        sa.Column('end_time', sa.TIMESTAMP(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('evaluation_mode', sa.String(length=20), server_default='virtual', nullable=True),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('grade_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Campos de escopo
        sa.Column('municipalities', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('schools', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('classes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('course', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=50), nullable=True),
        sa.Column('subjects_info', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='agendada', nullable=True),
        sa.Column('grade_calculation_type', sa.String(length=20), server_default='complex', nullable=True),
        
        # Limite de participantes
        sa.Column('max_participantes', sa.Integer(), nullable=True),
        
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['subject'], ['subject.id'], ),
        sa.ForeignKeyConstraint(['grade_id'], ['grade.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Criar índices para competitions
    op.create_index(op.f('ix_competitions_created_by'), 'competitions', ['created_by'], unique=False)
    op.create_index(op.f('ix_competitions_subject'), 'competitions', ['subject'], unique=False)
    op.create_index(op.f('ix_competitions_grade_id'), 'competitions', ['grade_id'], unique=False)
    op.create_index(op.f('ix_competitions_status'), 'competitions', ['status'], unique=False)
    
    # Criar tabela competition_enrollments
    op.create_table('competition_enrollments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('competition_id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('enrolled_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='inscrito', nullable=True),
        sa.ForeignKeyConstraint(['competition_id'], ['competitions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['student.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('competition_id', 'student_id', name='uq_competition_student')
    )
    
    # Criar índices para competition_enrollments
    op.create_index(op.f('ix_competition_enrollments_competition_id'), 'competition_enrollments', ['competition_id'], unique=False)
    op.create_index(op.f('ix_competition_enrollments_student_id'), 'competition_enrollments', ['student_id'], unique=False)
    op.create_index(op.f('ix_competition_enrollments_status'), 'competition_enrollments', ['status'], unique=False)
    
    # Criar tabela competition_results
    op.create_table('competition_results',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('competition_id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        
        # Dados de cálculo
        sa.Column('correct_answers', sa.Integer(), nullable=False),
        sa.Column('total_questions', sa.Integer(), nullable=False),
        sa.Column('score_percentage', sa.Float(), nullable=False),
        sa.Column('grade', sa.Float(), nullable=False),
        sa.Column('proficiency', sa.Float(), nullable=False),
        sa.Column('classification', sa.String(length=50), nullable=False),
        
        # Campos específicos de competição
        sa.Column('posicao', sa.Integer(), nullable=True),
        sa.Column('moedas_ganhas', sa.Integer(), server_default='0', nullable=True),
        sa.Column('tempo_gasto', sa.Integer(), nullable=True),
        sa.Column('acertos', sa.Integer(), nullable=False),
        sa.Column('erros', sa.Integer(), nullable=False),
        sa.Column('em_branco', sa.Integer(), nullable=False),
        
        # Metadados
        sa.Column('calculated_at', sa.TIMESTAMP(), nullable=True),
        
        sa.ForeignKeyConstraint(['competition_id'], ['competitions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['student.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['test_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Criar índices para competition_results
    op.create_index(op.f('ix_competition_results_competition_id'), 'competition_results', ['competition_id'], unique=False)
    op.create_index(op.f('ix_competition_results_student_id'), 'competition_results', ['student_id'], unique=False)
    op.create_index(op.f('ix_competition_results_session_id'), 'competition_results', ['session_id'], unique=False)
    op.create_index(op.f('ix_competition_results_posicao'), 'competition_results', ['posicao'], unique=False)
    op.create_index(op.f('ix_competition_results_grade'), 'competition_results', ['grade'], unique=False)


def downgrade():
    # Remover índices de competition_results
    op.drop_index(op.f('ix_competition_results_grade'), table_name='competition_results')
    op.drop_index(op.f('ix_competition_results_posicao'), table_name='competition_results')
    op.drop_index(op.f('ix_competition_results_session_id'), table_name='competition_results')
    op.drop_index(op.f('ix_competition_results_student_id'), table_name='competition_results')
    op.drop_index(op.f('ix_competition_results_competition_id'), table_name='competition_results')
    
    # Remover tabela competition_results
    op.drop_table('competition_results')
    
    # Remover índices de competition_enrollments
    op.drop_index(op.f('ix_competition_enrollments_status'), table_name='competition_enrollments')
    op.drop_index(op.f('ix_competition_enrollments_student_id'), table_name='competition_enrollments')
    op.drop_index(op.f('ix_competition_enrollments_competition_id'), table_name='competition_enrollments')
    
    # Remover tabela competition_enrollments
    op.drop_table('competition_enrollments')
    
    # Remover índices de competitions
    op.drop_index(op.f('ix_competitions_status'), table_name='competitions')
    op.drop_index(op.f('ix_competitions_grade_id'), table_name='competitions')
    op.drop_index(op.f('ix_competitions_subject'), table_name='competitions')
    op.drop_index(op.f('ix_competitions_created_by'), table_name='competitions')
    
    # Remover tabela competitions
    op.drop_table('competitions')

