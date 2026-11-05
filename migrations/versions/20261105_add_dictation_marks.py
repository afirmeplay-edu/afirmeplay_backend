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


def _city_schemas_with_written_question(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'reading_written_test_question' "
            "AND table_schema LIKE 'city_%' "
            "ORDER BY table_schema"
        )
    )
    return [row[0] for row in rows]


def _safe_city_schema(schema: str) -> str:
    if not schema.startswith("city_") or not schema.replace("_", "").isalnum():
        raise ValueError(f"Nome de schema inválido: {schema}")
    return schema


def upgrade():
    op.add_column(
        "question",
        sa.Column("dictation_marks", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        schema="public",
    )
    bind = op.get_bind()
    for schema in _city_schemas_with_written_question(bind):
        schema = _safe_city_schema(schema)
        bind.execute(
            sa.text(
                f'ALTER TABLE "{schema}".reading_written_test_question '
                "ADD COLUMN IF NOT EXISTS dictation_marks JSON"
            )
        )


def downgrade():
    bind = op.get_bind()
    for schema in _city_schemas_with_written_question(bind):
        schema = _safe_city_schema(schema)
        bind.execute(
            sa.text(
                f'ALTER TABLE "{schema}".reading_written_test_question '
                "DROP COLUMN IF EXISTS dictation_marks"
            )
        )
    op.drop_column("question", "dictation_marks", schema="public")
