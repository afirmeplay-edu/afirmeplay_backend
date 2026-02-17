"""Add fields to competition_templates and edition fields to competitions.

Esta migration complementa as tabelas criadas em add_competitions_tables /
ensure_competitions_20260204, adicionando os campos planejados para
CompetitionTemplate (Etapa 6) e campos auxiliares de edição em Competition.

Revision ID: add_competition_templates
Revises: ensure_competitions_20260204
Create Date: 2026-02-12
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
# Depende de e9f68411fd2d para unificar a árvore (evitar multiple heads).
revision = "add_competition_templates"
down_revision = "e9f68411fd2d"
branch_labels = None
depends_on = None


def upgrade():
    # ---- competition_templates: adicionar campos conforme plano da Etapa 6 ----
    op.add_column(
        "competition_templates",
        sa.Column("name", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "competition_templates",
        sa.Column("subject_id", sa.String(), sa.ForeignKey("subject.id"), nullable=True),
    )
    op.add_column(
        "competition_templates",
        sa.Column("level", sa.Integer(), nullable=True),
    )
    op.add_column(
        "competition_templates",
        sa.Column(
            "scope",
            sa.String(),
            nullable=False,
            server_default="individual",
        ),
    )
    op.add_column(
        "competition_templates",
        sa.Column("scope_filter", sa.JSON(), nullable=True),
    )
    op.add_column(
        "competition_templates",
        sa.Column("recurrence", sa.String(), nullable=False, server_default="weekly"),
    )
    op.add_column(
        "competition_templates",
        sa.Column(
            "question_mode",
            sa.String(),
            nullable=False,
            server_default="auto_random",
        ),
    )
    op.add_column(
        "competition_templates",
        sa.Column("question_rules", sa.JSON(), nullable=True),
    )
    op.add_column(
        "competition_templates",
        sa.Column("reward_config", sa.JSON(), nullable=True),
    )
    op.add_column(
        "competition_templates",
        sa.Column(
            "ranking_criteria",
            sa.String(),
            nullable=False,
            server_default="nota",
        ),
    )
    op.add_column(
        "competition_templates",
        sa.Column(
            "ranking_tiebreaker",
            sa.String(),
            nullable=False,
            server_default="tempo_entrega",
        ),
    )
    op.add_column(
        "competition_templates",
        sa.Column(
            "ranking_visibility",
            sa.String(),
            nullable=False,
            server_default="final",
        ),
    )
    op.add_column(
        "competition_templates",
        sa.Column("max_participants", sa.Integer(), nullable=True),
    )
    op.add_column(
        "competition_templates",
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
    )
    op.add_column(
        "competition_templates",
        sa.Column(
            "created_by",
            sa.String(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "competition_templates",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
    )
    op.add_column(
        "competition_templates",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
    )

    # Índices auxiliares para consultas do job automático
    op.create_index(
        "ix_competition_templates_subject",
        "competition_templates",
        ["subject_id"],
        unique=False,
    )
    op.create_index(
        "ix_competition_templates_recurrence",
        "competition_templates",
        ["recurrence"],
        unique=False,
    )
    op.create_index(
        "ix_competition_templates_active",
        "competition_templates",
        ["active"],
        unique=False,
    )

    # ---- competitions: adicionar campos de edição/série ----
    op.add_column(
        "competitions",
        sa.Column("edition_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "competitions",
        sa.Column("edition_series", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_competitions_edition_lookup",
        "competitions",
        ["edition_series", "subject_id", "recurrence", "edition_number"],
        unique=False,
    )


def downgrade():
    # Remover índice e colunas de competitions
    op.drop_index("ix_competitions_edition_lookup", table_name="competitions")
    op.drop_column("competitions", "edition_series")
    op.drop_column("competitions", "edition_number")

    # Remover índices de competition_templates
    op.drop_index("ix_competition_templates_active", table_name="competition_templates")
    op.drop_index(
        "ix_competition_templates_recurrence", table_name="competition_templates"
    )
    op.drop_index(
        "ix_competition_templates_subject", table_name="competition_templates"
    )

    # Remover colunas de competition_templates
    op.drop_column("competition_templates", "updated_at")
    op.drop_column("competition_templates", "created_at")
    op.drop_column("competition_templates", "created_by")
    op.drop_column("competition_templates", "active")
    op.drop_column("competition_templates", "max_participants")
    op.drop_column("competition_templates", "ranking_visibility")
    op.drop_column("competition_templates", "ranking_tiebreaker")
    op.drop_column("competition_templates", "ranking_criteria")
    op.drop_column("competition_templates", "reward_config")
    op.drop_column("competition_templates", "question_rules")
    op.drop_column("competition_templates", "question_mode")
    op.drop_column("competition_templates", "recurrence")
    op.drop_column("competition_templates", "scope_filter")
    op.drop_column("competition_templates", "scope")
    op.drop_column("competition_templates", "level")
    op.drop_column("competition_templates", "subject_id")
    op.drop_column("competition_templates", "name")

