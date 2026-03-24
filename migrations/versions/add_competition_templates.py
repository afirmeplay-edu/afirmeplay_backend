"""Add edition fields to competitions (competition_templates removido do sistema).

Revision ID: add_competition_templates
Revises: e9f68411fd2d
Create Date: 2026-02-12

Nota: competition_templates foi removido do sistema; esta migration apenas
adiciona edition_number e edition_series em competitions quando não existirem.
"""

from alembic import op
import sqlalchemy as sa

revision = "add_competition_templates"
down_revision = "e9f68411fd2d"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    r = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": table_name},
    )
    return r.scalar() is not None


def _column_exists(connection, table_name, column_name):
    r = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :tname AND column_name = :cname"
        ),
        {"tname": table_name, "cname": column_name},
    )
    return r.scalar() is not None


def _index_exists(connection, index_name):
    r = connection.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :name"
        ),
        {"name": index_name},
    )
    return r.scalar() is not None


def upgrade():
    connection = op.get_bind()
    if not _table_exists(connection, "competitions"):
        return
    if not _column_exists(connection, "competitions", "edition_number"):
        op.add_column(
            "competitions",
            sa.Column("edition_number", sa.Integer(), nullable=True),
        )
    if not _column_exists(connection, "competitions", "edition_series"):
        op.add_column(
            "competitions",
            sa.Column("edition_series", sa.String(), nullable=True),
        )
    if not _index_exists(connection, "ix_competitions_edition_lookup"):
        op.create_index(
            "ix_competitions_edition_lookup",
            "competitions",
            ["edition_series", "subject_id", "recurrence", "edition_number"],
            unique=False,
        )


def downgrade():
    connection = op.get_bind()
    if _index_exists(connection, "ix_competitions_edition_lookup"):
        op.drop_index("ix_competitions_edition_lookup", table_name="competitions")
    if _table_exists(connection, "competitions"):
        if _column_exists(connection, "competitions", "edition_series"):
            op.drop_column("competitions", "edition_series")
        if _column_exists(connection, "competitions", "edition_number"):
            op.drop_column("competitions", "edition_number")

