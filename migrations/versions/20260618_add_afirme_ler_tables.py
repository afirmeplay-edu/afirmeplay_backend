# -*- coding: utf-8 -*-
"""Add Afirme Ler reading texts, questions and word lists (public schema)

Revision ID: add_afirme_ler_tables
Revises: add_city_plan_code
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_afirme_ler_tables"
down_revision = "add_city_plan_code"
branch_labels = None
depends_on = None

_SCOPE_CHECK = "scope_type IN ('GLOBAL', 'CITY', 'PRIVATE')"
_DIFFICULTY_CHECK = (
    "difficulty_level IN ('VERY_EASY', 'EASY', 'MEDIUM', 'HARD', 'VERY_HARD')"
)
_KIND_CHECK = "kind IN ('PALAVRAS', 'POUCO_COMUNS')"


def upgrade():
    op.create_table(
        "reading_text",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("grade_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("difficulty_level", sa.String(length=20), nullable=False),
        sa.Column(
            "target_skills",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("source", sa.String(length=500), nullable=True),
        sa.Column("is_calibrated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="GLOBAL"),
        sa.Column("owner_city_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["grade_id"], ["public.grade.id"]),
        sa.ForeignKeyConstraint(["owner_city_id"], ["public.city.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["public.users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"]),
        sa.CheckConstraint(_SCOPE_CHECK, name="ck_reading_text_scope_type"),
        sa.CheckConstraint(_DIFFICULTY_CHECK, name="ck_reading_text_difficulty_level"),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index(
        "ix_reading_text_grade_id",
        "reading_text",
        ["grade_id"],
        schema="public",
    )
    op.create_index(
        "ix_reading_text_scope_type",
        "reading_text",
        ["scope_type"],
        schema="public",
    )
    op.create_index(
        "ix_reading_text_owner_city_id",
        "reading_text",
        ["owner_city_id"],
        schema="public",
    )

    op.create_table(
        "reading_text_question",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("reading_text_id", sa.String(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column(
            "options",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("correct_option", sa.Integer(), nullable=True),
        sa.Column("descriptor", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reading_text_id"],
            ["public.reading_text.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index(
        "ix_reading_text_question_reading_text_id",
        "reading_text_question",
        ["reading_text_id"],
        schema="public",
    )

    op.create_table(
        "reading_word_list",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="PALAVRAS"),
        sa.Column(
            "items",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="GLOBAL"),
        sa.Column("owner_city_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_city_id"], ["public.city.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["public.users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"]),
        sa.CheckConstraint(_SCOPE_CHECK, name="ck_reading_word_list_scope_type"),
        sa.CheckConstraint(_KIND_CHECK, name="ck_reading_word_list_kind"),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index(
        "ix_reading_word_list_kind",
        "reading_word_list",
        ["kind"],
        schema="public",
    )
    op.create_index(
        "ix_reading_word_list_scope_type",
        "reading_word_list",
        ["scope_type"],
        schema="public",
    )


def downgrade():
    op.drop_index("ix_reading_word_list_scope_type", table_name="reading_word_list", schema="public")
    op.drop_index("ix_reading_word_list_kind", table_name="reading_word_list", schema="public")
    op.drop_table("reading_word_list", schema="public")

    op.drop_index(
        "ix_reading_text_question_reading_text_id",
        table_name="reading_text_question",
        schema="public",
    )
    op.drop_table("reading_text_question", schema="public")

    op.drop_index("ix_reading_text_owner_city_id", table_name="reading_text", schema="public")
    op.drop_index("ix_reading_text_scope_type", table_name="reading_text", schema="public")
    op.drop_index("ix_reading_text_grade_id", table_name="reading_text", schema="public")
    op.drop_table("reading_text", schema="public")
