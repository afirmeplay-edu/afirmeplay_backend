# -*- coding: utf-8 -*-
"""Origem da questão em public.question (afirme_play | afirme_ler).

Questões existentes ficam 'afirme_play'. Questões criadas pelo Afirme Ler
gravam 'afirme_ler' e não aparecem nas listagens do Afirme Play.

Revision ID: 20261023_question_origin
Revises: 20261022_subjective_subturmas
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20261023_question_origin"
down_revision = "20261022_subjective_subturmas"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "question",
        sa.Column(
            "origin",
            sa.String(length=20),
            nullable=False,
            server_default="afirme_play",
        ),
        schema="public",
    )
    op.create_check_constraint(
        "ck_question_origin",
        "question",
        "origin IN ('afirme_play', 'afirme_ler')",
        schema="public",
    )
    op.create_index(
        "ix_question_origin",
        "question",
        ["origin"],
        schema="public",
    )


def downgrade():
    op.drop_index("ix_question_origin", table_name="question", schema="public")
    op.drop_constraint("ck_question_origin", "question", type_="check", schema="public")
    op.drop_column("question", "origin", schema="public")
