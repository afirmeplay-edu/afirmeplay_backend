# -*- coding: utf-8 -*-
"""Megafones do aplicador (dictation_marks) em question e reading_written_test_question.

Revision ID: 20261105_dictation_marks
Revises: merge_writing_stimulus_logistics
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261105_dictation_marks"
down_revision = "merge_writing_stimulus_logistics"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "question",
        sa.Column("dictation_marks", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        schema="public",
    )
    # Tabelas tenant são criadas/atualizadas via ddl por município; este ALTER
    # cobre o schema tenant ativo da migration (quando aplicável).
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'tenant'
                      AND table_name = 'reading_written_test_question'
                ) THEN
                    ALTER TABLE tenant.reading_written_test_question
                        ADD COLUMN IF NOT EXISTS dictation_marks JSON;
                END IF;
            END $$;
            """
        )
    )


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'tenant'
                      AND table_name = 'reading_written_test_question'
                      AND column_name = 'dictation_marks'
                ) THEN
                    ALTER TABLE tenant.reading_written_test_question
                        DROP COLUMN dictation_marks;
                END IF;
            END $$;
            """
        )
    )
    op.drop_column("question", "dictation_marks", schema="public")
