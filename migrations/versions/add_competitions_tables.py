"""Add competitions and all competition-related tables (Etapa 2).

Cria: competition_templates (se não existir), competitions, competition_enrollments,
competition_rewards, competition_results, competition_ranking_payouts.

Revision ID: add_competitions_tables
Revises: 7151d9971a90
Create Date: 2025-01-XX 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_competitions_tables'
down_revision = '7151d9971a90'
branch_labels = None
depends_on = None


def _competition_templates_exists(connection):
    result = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'competition_templates'"
        )
    )
    return result.scalar() is not None


def upgrade():
    connection = op.get_bind()

    # ---- competition_templates (se ainda não existir) ----
    if not _competition_templates_exists(connection):
        op.create_table(
            'competition_templates',
            sa.Column('id', sa.String(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    # ---- Tabela: competitions ----
    op.create_table(
        'competitions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('test_id', sa.String(), sa.ForeignKey('test.id'), nullable=True),
        sa.Column('subject_id', sa.String(), sa.ForeignKey('subject.id'), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('scope', sa.String(), nullable=False, server_default='individual'),
        sa.Column('scope_filter', sa.JSON(), nullable=True),
        sa.Column('enrollment_start', sa.TIMESTAMP(), nullable=False),
        sa.Column('enrollment_end', sa.TIMESTAMP(), nullable=False),
        sa.Column('application', sa.TIMESTAMP(), nullable=False),
        sa.Column('expiration', sa.TIMESTAMP(), nullable=False),
        sa.Column('timezone', sa.String(), nullable=False, server_default='America/Sao_Paulo'),
        sa.Column('question_mode', sa.String(), nullable=False, server_default='auto_random'),
        sa.Column('question_rules', sa.JSON(), nullable=True),
        sa.Column('reward_config', sa.JSON(), nullable=False),
        sa.Column('ranking_criteria', sa.String(), nullable=False, server_default='nota'),
        sa.Column('ranking_tiebreaker', sa.String(), nullable=False, server_default='tempo_entrega'),
        sa.Column('ranking_visibility', sa.String(), nullable=False, server_default='final'),
        sa.Column('max_participants', sa.Integer(), nullable=True),
        sa.Column('recurrence', sa.String(), nullable=False, server_default='manual'),
        sa.Column('template_id', sa.String(), sa.ForeignKey('competition_templates.id'), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='rascunho'),
        sa.Column('created_by', sa.String(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_competitions_created_by'), 'competitions', ['created_by'], unique=False)
    op.create_index(op.f('ix_competitions_subject'), 'competitions', ['subject_id'], unique=False)
    op.create_index(op.f('ix_competitions_grade_id'), 'competitions', ['level'], unique=False)
    op.create_index(op.f('ix_competitions_status'), 'competitions', ['status'], unique=False)

    # ---- Tabela: competition_enrollments ----
    op.create_table(
        'competition_enrollments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('competition_id', sa.String(), sa.ForeignKey('competitions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.String(), sa.ForeignKey('student.id', ondelete='CASCADE'), nullable=False),
        sa.Column('enrolled_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='inscrito'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('competition_id', 'student_id', name='uq_competition_enrollments_competition_student'),
    )
    op.create_index('ix_competition_enrollments_competition_id', 'competition_enrollments', ['competition_id'], unique=False)
    op.create_index('ix_competition_enrollments_student_id', 'competition_enrollments', ['student_id'], unique=False)
    op.create_index('ix_competition_enrollments_status', 'competition_enrollments', ['status'], unique=False)

    # ---- Tabela: competition_rewards ----
    op.create_table(
        'competition_rewards',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('competition_id', sa.String(), sa.ForeignKey('competitions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.String(), sa.ForeignKey('student.id', ondelete='CASCADE'), nullable=False),
        sa.Column('participation_paid_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('competition_id', 'student_id', name='uq_competition_rewards_competition_student'),
    )
    op.create_index('ix_competition_rewards_competition_id', 'competition_rewards', ['competition_id'], unique=False)
    op.create_index('ix_competition_rewards_student_id', 'competition_rewards', ['student_id'], unique=False)

    # ---- Tabela: competition_results ----
    op.create_table(
        'competition_results',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('competition_id', sa.String(), sa.ForeignKey('competitions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.String(), sa.ForeignKey('student.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.String(), sa.ForeignKey('test_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('correct_answers', sa.Integer(), nullable=False),
        sa.Column('total_questions', sa.Integer(), nullable=False),
        sa.Column('score_percentage', sa.Float(), nullable=False),
        sa.Column('grade', sa.Float(), nullable=False),
        sa.Column('proficiency', sa.Float(), nullable=True),
        sa.Column('classification', sa.String(), nullable=True),
        sa.Column('posicao', sa.Integer(), nullable=False),
        sa.Column('moedas_ganhas', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tempo_gasto', sa.Integer(), nullable=True),
        sa.Column('acertos', sa.Integer(), nullable=False),
        sa.Column('erros', sa.Integer(), nullable=False),
        sa.Column('em_branco', sa.Integer(), nullable=False),
        sa.Column('calculated_at', sa.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('competition_id', 'student_id', name='uq_competition_results_competition_student'),
    )
    op.create_index('ix_competition_results_competition_id', 'competition_results', ['competition_id'], unique=False)
    op.create_index('ix_competition_results_student_id', 'competition_results', ['student_id'], unique=False)
    op.create_index('ix_competition_results_posicao', 'competition_results', ['posicao'], unique=False)

    # ---- Tabela: competition_ranking_payouts ----
    op.create_table(
        'competition_ranking_payouts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('competition_id', sa.String(), sa.ForeignKey('competitions.id'), nullable=False),
        sa.Column('student_id', sa.String(), sa.ForeignKey('student.id'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('paid_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('competition_id', 'student_id', name='uq_competition_ranking_payouts_competition_student'),
    )
    op.create_index('ix_competition_ranking_payouts_competition_id', 'competition_ranking_payouts', ['competition_id'], unique=False)
    op.create_index('ix_competition_ranking_payouts_student_id', 'competition_ranking_payouts', ['student_id'], unique=False)


def downgrade():
    # Remover tabelas na ordem inversa (respeitando FKs)
    op.drop_table('competition_ranking_payouts')
    op.drop_table('competition_results')
    op.drop_table('competition_rewards')
    op.drop_table('competition_enrollments')

    op.drop_index(op.f('ix_competitions_status'), table_name='competitions')
    op.drop_index(op.f('ix_competitions_grade_id'), table_name='competitions')
    op.drop_index(op.f('ix_competitions_subject'), table_name='competitions')
    op.drop_index(op.f('ix_competitions_created_by'), table_name='competitions')
    op.drop_table('competitions')

    # Não removemos competition_templates no downgrade pois pode ter sido criada por outra migration

