# -*- coding: utf-8 -*-
"""Estímulo do ditado do Afirme Ler: palavra falada ou descrição de figura.

Revision ID: 20261029_writing_stimulus
Revises: 20261023_question_origin
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa


revision = "20261029_writing_stimulus"
down_revision = "20261023_question_origin"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "question",
        sa.Column("writing_stimulus", sa.String(length=16), nullable=True),
        schema="public",
    )
    op.add_column(
        "question",
        sa.Column("writing_reference", sa.Text(), nullable=True),
        schema="public",
    )


def downgrade():
    op.drop_column("question", "writing_reference", schema="public")
    op.drop_column("question", "writing_stimulus", schema="public")
