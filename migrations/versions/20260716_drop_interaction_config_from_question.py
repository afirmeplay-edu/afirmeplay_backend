# -*- coding: utf-8 -*-
"""Remove interaction_config de public.question (avaliação subjetiva agora é entidade própria)

Revision ID: 20260716_drop_interaction_config_from_question
Revises: 20260715_drop_skill_text_from_question
Create Date: 2026-07-16

A avaliação subjetiva deixou de reaproveitar Test/Question: agora é uma entidade
própria (tenant.subjective_tests/subjective_questions, ver migrations_multitenant/
0005_add_subjective_test_entity.py). `Question.interaction_config` não é mais usado
por nenhum fluxo e pode ser removido.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260716_drop_interaction_config_from_question"
down_revision = "20260715_drop_skill_text_from_question"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("question", "interaction_config", schema="public")


def downgrade():
    op.add_column("question", sa.Column("interaction_config", sa.JSON(), nullable=True), schema="public")
