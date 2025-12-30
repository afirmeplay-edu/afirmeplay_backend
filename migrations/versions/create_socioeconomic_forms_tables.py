"""Create socioeconomic forms tables

Revision ID: socioeconomic_forms_001
Revises: 75a6b30782f9
Create Date: 2025-12-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'socioeconomic_forms_001'
down_revision = '75a6b30782f9'  # Ajuste para a última migration do seu projeto
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela forms
    op.create_table('forms',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('form_type', sa.String(length=50), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('target_groups', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('selected_schools', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('selected_grades', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('selected_tecadmin_users', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('deadline', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_form_type', 'forms', ['form_type'])
    op.create_index('idx_is_active', 'forms', ['is_active'])
    op.create_index('idx_created_at', 'forms', ['created_at'])
    
    # Criar tabela form_questions
    op.create_table('form_questions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('form_id', sa.String(), nullable=False),
        sa.Column('question_id', sa.String(length=50), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('options', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('sub_questions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('min_value', sa.Integer(), nullable=True),
        sa.Column('max_value', sa.Integer(), nullable=True),
        sa.Column('option_id', sa.String(length=50), nullable=True),
        sa.Column('option_text', sa.String(length=255), nullable=True),
        sa.Column('required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('question_order', sa.Integer(), nullable=False),
        sa.Column('depends_on', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_form_id', 'form_questions', ['form_id'])
    op.create_index('idx_question_order', 'form_questions', ['question_order'])
    
    # Criar tabela form_recipients
    op.create_table('form_recipients',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('form_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('school_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('sent_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['school.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('form_id', 'user_id', name='unique_form_user_recipient')
    )
    op.create_index('idx_form_id_recipient', 'form_recipients', ['form_id'])
    op.create_index('idx_user_id_recipient', 'form_recipients', ['user_id'])
    op.create_index('idx_status_recipient', 'form_recipients', ['status'])
    
    # Criar tabela form_responses
    op.create_table('form_responses',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('form_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('recipient_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='in_progress'),
        sa.Column('responses', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('progress', sa.Numeric(5, 2), nullable=False, server_default='0.00'),
        sa.Column('started_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('time_spent', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_id'], ['form_recipients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('form_id', 'user_id', name='unique_form_user_response')
    )
    op.create_index('idx_form_id_response', 'form_responses', ['form_id'])
    op.create_index('idx_user_id_response', 'form_responses', ['user_id'])
    op.create_index('idx_status_response', 'form_responses', ['status'])
    op.create_index('idx_completed_at', 'form_responses', ['completed_at'])


def downgrade():
    # Remover tabelas na ordem inversa (respeitando foreign keys)
    op.drop_table('form_responses')
    op.drop_table('form_recipients')
    op.drop_table('form_questions')
    op.drop_table('forms')

