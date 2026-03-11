# -*- coding: utf-8 -*-
"""Add answer_sheet_generation_jobs table (public) and last_generation_job_id on answer_sheet_gabaritos

Tabela em public para persistir estado do job de geração de cartões (visível por todas as instâncias).
Coluna last_generation_job_id nos gabaritos (por schema city_xxx), preenchida apenas quando a rota
generate é chamada.

Revision ID: add_answer_sheet_gen_jobs
Revises: add_competition_templates
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'add_answer_sheet_gen_jobs'
down_revision = 'add_competition_templates'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1) Criar tabela em public para jobs de geração de cartões
    op.create_table(
        'answer_sheet_generation_jobs',
        sa.Column('job_id', sa.String(36), nullable=False),
        sa.Column('city_id', sa.String(36), nullable=False),
        sa.Column('gabarito_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('task_ids', JSONB, nullable=True),  # array de strings (IDs das tasks Celery)
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('completed', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('successful', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('failed', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(20), server_default=sa.text("'processing'"), nullable=False),
        sa.Column('progress_current', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('progress_percentage', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('scope_type', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('total_students_generated', sa.Integer(), nullable=True),
        sa.Column('classes_generated', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('job_id'),
        schema='public'
    )
    op.create_index(
        op.f('ix_answer_sheet_generation_jobs_city_id'),
        'answer_sheet_generation_jobs',
        ['city_id'],
        unique=False,
        schema='public'
    )
    op.create_index(
        op.f('ix_answer_sheet_generation_jobs_gabarito_id'),
        'answer_sheet_generation_jobs',
        ['gabarito_id'],
        unique=False,
        schema='public'
    )

    # 2) Adicionar last_generation_job_id em answer_sheet_gabaritos em cada schema city_xxx
    r = conn.execute(sa.text(
        "SELECT DISTINCT table_schema FROM information_schema.tables "
        "WHERE table_name = 'answer_sheet_gabaritos'"
    ))
    schemas = [row[0] for row in r]
    for schema in schemas:
        try:
            conn.execute(sa.text(
                f'ALTER TABLE "{schema}".answer_sheet_gabaritos '
                'ADD COLUMN IF NOT EXISTS last_generation_job_id VARCHAR(36) NULL'
            ))
        except Exception as e:
            import logging
            logging.warning("Migration add_answer_sheet_gen_jobs: schema %s: %s", schema, e)


def downgrade():
    conn = op.get_bind()

    # Remover coluna last_generation_job_id de cada schema
    r = conn.execute(sa.text(
        "SELECT DISTINCT table_schema FROM information_schema.tables "
        "WHERE table_name = 'answer_sheet_gabaritos'"
    ))
    schemas = [row[0] for row in r]
    for schema in schemas:
        try:
            conn.execute(sa.text(
                f'ALTER TABLE "{schema}".answer_sheet_gabaritos '
                'DROP COLUMN IF EXISTS last_generation_job_id'
            ))
        except Exception:
            pass

    # Remover tabela em public
    op.drop_index(
        op.f('ix_answer_sheet_generation_jobs_gabarito_id'),
        table_name='answer_sheet_generation_jobs',
        schema='public'
    )
    op.drop_index(
        op.f('ix_answer_sheet_generation_jobs_city_id'),
        table_name='answer_sheet_generation_jobs',
        schema='public'
    )
    op.drop_table('answer_sheet_generation_jobs', schema='public')
