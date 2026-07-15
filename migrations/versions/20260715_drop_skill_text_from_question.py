# -*- coding: utf-8 -*-
"""Remove skill_text de public.question (avaliação subjetiva usa a mesma tabela skills)

Revision ID: 20260715_drop_skill_text_from_question
Revises: 20260714_add_subjective_question_fields
Create Date: 2026-07-15

A avaliação subjetiva não usa mais habilidade digitada livremente: as questões
subjetivas passam a usar `Question.skill`, a mesma referência à tabela `skills`
já usada pelas avaliações online. `interaction_config` não é afetado por esta
migração e continua existindo (guarda a configuração dos 9 tipos de interação).
"""
from alembic import op
import sqlalchemy as sa

revision = "20260715_drop_skill_text_from_question"
down_revision = "20260714_add_subjective_question_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("question", "skill_text", schema="public")


def downgrade():
    op.add_column("question", sa.Column("skill_text", sa.String(), nullable=True), schema="public")
