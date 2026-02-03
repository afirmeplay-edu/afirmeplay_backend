# -*- coding: utf-8 -*-
"""Add student_coins and coin_transactions tables (Etapa 1 - Sistema de Moedas)

Revision ID: add_student_coins_system
Revises: 39bcc7ca5bcb
Create Date: 2025-02-03

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_student_coins_system'
down_revision = 'e65e9db85b23'
branch_labels = None
depends_on = None


def upgrade():
    # Tabela: student_coins
    op.create_table(
        'student_coins',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('balance', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['student_id'], ['student.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('student_id', name='uq_student_coins_student_id'),
    )

    # Tabela: coin_transactions
    op.create_table(
        'coin_transactions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_before', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('competition_id', sa.String(), nullable=True),
        sa.Column('test_session_id', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['student_id'], ['student.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_session_id'], ['test_sessions.id'], ondelete='SET NULL'),
    )

    op.create_index('idx_coin_transactions_student_id', 'coin_transactions', ['student_id'])
    op.create_index('idx_coin_transactions_created_at', 'coin_transactions', ['created_at'])


def downgrade():
    op.drop_index('idx_coin_transactions_created_at', table_name='coin_transactions')
    op.drop_index('idx_coin_transactions_student_id', table_name='coin_transactions')
    op.drop_table('coin_transactions')
    op.drop_table('student_coins')
