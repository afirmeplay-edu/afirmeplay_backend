# -*- coding: utf-8 -*-
"""Rename reading_word_list.kind PALAVRAS → PALAVRAS_CONHECIDAS

Revision ID: 20260820_afirme_ler_known_words
Revises: 20260716_drop_interaction_config_from_question
Create Date: 2026-08-20
"""
from alembic import op


revision = "20260820_afirme_ler_known_words"
down_revision = "20260716_drop_interaction_config_from_question"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE public.reading_word_list "
        "DROP CONSTRAINT IF EXISTS ck_reading_word_list_kind"
    )
    op.execute(
        "UPDATE public.reading_word_list "
        "SET kind = 'PALAVRAS_CONHECIDAS' WHERE kind = 'PALAVRAS'"
    )
    op.execute(
        "ALTER TABLE public.reading_word_list "
        "ALTER COLUMN kind SET DEFAULT 'PALAVRAS_CONHECIDAS'"
    )
    op.execute(
        "ALTER TABLE public.reading_word_list "
        "ADD CONSTRAINT ck_reading_word_list_kind "
        "CHECK (kind IN ('PALAVRAS_CONHECIDAS', 'POUCO_COMUNS'))"
    )


def downgrade():
    op.execute(
        "ALTER TABLE public.reading_word_list "
        "DROP CONSTRAINT IF EXISTS ck_reading_word_list_kind"
    )
    op.execute(
        "UPDATE public.reading_word_list "
        "SET kind = 'PALAVRAS' WHERE kind = 'PALAVRAS_CONHECIDAS'"
    )
    op.execute(
        "ALTER TABLE public.reading_word_list "
        "ALTER COLUMN kind SET DEFAULT 'PALAVRAS'"
    )
    op.execute(
        "ALTER TABLE public.reading_word_list "
        "ADD CONSTRAINT ck_reading_word_list_kind "
        "CHECK (kind IN ('PALAVRAS', 'POUCO_COMUNS'))"
    )
