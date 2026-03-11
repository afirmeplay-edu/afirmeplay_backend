# -*- coding: utf-8 -*-
"""Cria tabela test_sessions no schema public se não existir.

Necessário para iniciar prova de competição (POST /competitions/:id/start) quando
a competição e o test estão em public.
Revision ID: add_test_sessions_public
Revises: add_test_tables_public
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import NUMERIC


revision = 'add_test_sessions_public'
down_revision = 'add_test_tables_public'
branch_labels = None
depends_on = None


def _table_exists(connection, schema, table_name):
    r = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name"
        ),
        {"schema": schema, "name": table_name},
    )
    return r.scalar() is not None


def upgrade():
    connection = op.get_bind()
    schema = 'public'

    if not _table_exists(connection, schema, 'test_sessions'):
        op.create_table(
            'test_sessions',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('student_id', sa.String(), nullable=False),
            sa.Column('test_id', sa.String(), nullable=False),
            sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('actual_start_time', sa.TIMESTAMP(), nullable=True),
            sa.Column('submitted_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('time_limit_minutes', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(20), nullable=True, server_default='em_andamento'),
            sa.Column('total_questions', sa.Integer(), nullable=True),
            sa.Column('correct_answers', sa.Integer(), nullable=True),
            sa.Column('score', sa.Float(), nullable=True),
            sa.Column('grade', sa.Float(), nullable=True),
            sa.Column('manual_score', NUMERIC(5, 2), nullable=True),
            sa.Column('feedback', sa.Text(), nullable=True),
            sa.Column('corrected_by', sa.String(), nullable=True),
            sa.Column('corrected_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('updated_at', sa.TIMESTAMP(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            schema=schema,
        )
        op.create_index('ix_test_sessions_student_id', 'test_sessions', ['student_id'], unique=False, schema=schema)
        op.create_index('ix_test_sessions_test_id', 'test_sessions', ['test_id'], unique=False, schema=schema)
        op.create_index('ix_test_sessions_status', 'test_sessions', ['status'], unique=False, schema=schema)


def downgrade():
    pass
