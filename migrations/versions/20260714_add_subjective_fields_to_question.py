# -*- coding: utf-8 -*-
"""Add skill_text and interaction_config to public.question (avaliação subjetiva)

Revision ID: 20260714_add_subjective_question_fields
Revises: 20260625_add_city_id_to_mobile_directory
Create Date: 2026-07-14

skill_text: habilidade digitada livremente pelo usuário (avaliação subjetiva, sem tabela skills).
interaction_config: configuração da interação por tipo de questão (dissertativa, arrastar_soltar,
ligar_colunas, ordenacao, completar_lacunas, substituicao, destacar_trechos, escrita_matematica,
construcao_resposta). Usada apenas para documentar/exibir a questão; a correção é sempre manual.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260714_add_subjective_question_fields"
down_revision = "20260625_add_city_id_to_mobile_directory"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("question", sa.Column("skill_text", sa.String(), nullable=True), schema="public")
    op.add_column(
        "question",
        sa.Column("interaction_config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        schema="public",
    )


def downgrade():
    op.drop_column("question", "interaction_config", schema="public")
    op.drop_column("question", "skill_text", schema="public")
