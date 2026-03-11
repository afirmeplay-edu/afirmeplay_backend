# -*- coding: utf-8 -*-
"""Cria tabelas test e test_questions no schema public se não existirem.

Necessário para aleatorizar questões de competições que usam provas em public.
Revision ID: add_test_tables_public
Revises: merge_sidebar_drop_fk
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


revision = 'add_test_tables_public'
down_revision = 'merge_sidebar_drop_fk'
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

    if not _table_exists(connection, schema, 'test'):
        op.create_table(
            'test',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('title', sa.String(100), nullable=True),
            sa.Column('description', sa.String(500), nullable=True),
            sa.Column('intructions', sa.String(500), nullable=True),
            sa.Column('type', sa.String(), nullable=True),
            sa.Column('max_score', sa.Float(), nullable=True),
            sa.Column('time_limit', sa.TIMESTAMP(), nullable=True),
            sa.Column('end_time', sa.TIMESTAMP(), nullable=True),
            sa.Column('duration', sa.Integer(), nullable=True),
            sa.Column('evaluation_mode', sa.String(20), nullable=True, server_default='virtual'),
            sa.Column('created_by', sa.String(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('subject', sa.String(), nullable=True),
            sa.Column('grade_id', UUID(as_uuid=True), nullable=True),
            sa.Column('municipalities', JSON(), nullable=True),
            sa.Column('schools', JSON(), nullable=True),
            sa.Column('classes', JSON(), nullable=True),
            sa.Column('course', sa.String(100), nullable=True),
            sa.Column('model', sa.String(50), nullable=True),
            sa.Column('subjects_info', JSON(), nullable=True),
            sa.Column('status', sa.String(20), nullable=True, server_default='pendente'),
            sa.Column('grade_calculation_type', sa.String(20), nullable=True, server_default='complex'),
            sa.PrimaryKeyConstraint('id'),
            schema=schema,
        )
        op.create_index(op.f('ix_test_created_by'), 'test', ['created_by'], unique=False, schema=schema)
        op.create_index(op.f('ix_test_subject'), 'test', ['subject'], unique=False, schema=schema)

    if not _table_exists(connection, schema, 'test_questions'):
        op.create_table(
            'test_questions',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('test_id', sa.String(), nullable=False),
            sa.Column('question_id', sa.String(), nullable=False),
            sa.Column('order', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('test_id', 'question_id', name='uq_test_questions_test_question'),
            schema=schema,
        )
        op.create_index('ix_test_questions_test_id', 'test_questions', ['test_id'], unique=False, schema=schema)
        op.create_index('ix_test_questions_question_id', 'test_questions', ['question_id'], unique=False, schema=schema)
        op.create_index('ix_test_questions_order', 'test_questions', ['order'], unique=False, schema=schema)


def downgrade():
    # Não removemos tabelas para evitar perda de dados
    pass
