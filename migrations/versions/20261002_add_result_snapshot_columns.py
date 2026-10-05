# -*- coding: utf-8 -*-
"""Colunas de snapshot em answer_sheet_results e evaluation_results (city_%).

Escola/turma/série/matrícula no momento da participação.
Idempotente (ADD COLUMN IF NOT EXISTS).

Revision ID: 20261002_result_snapshots
Revises: merge_certificate_artworks_subturma
Create Date: 2026-10-02
"""
from alembic import op
import sqlalchemy as sa


revision = "20261002_result_snapshots"
down_revision = "merge_certificate_artworks_subturma"
branch_labels = None
depends_on = None

_SNAPSHOT_COLS = (
    ("school_id_snapshot", "VARCHAR(36)"),
    ("class_id_snapshot", "UUID"),
    ("grade_id_snapshot", "UUID"),
    ("enrollment_id_snapshot", "VARCHAR(36)"),
)

_COMMENTS = {
    "answer_sheet_results": {
        "school_id_snapshot": "Escola no momento da participação (imutável após preenchido).",
        "class_id_snapshot": "Turma no momento da participação (imutável após preenchido).",
        "grade_id_snapshot": "Série no momento da participação (imutável após preenchido).",
        "enrollment_id_snapshot": "Matrícula vigente no momento do resultado.",
    },
    "evaluation_results": {
        "school_id_snapshot": "Escola no momento da participação (imutável após preenchido).",
        "class_id_snapshot": "Turma no momento da participação (imutável após preenchido).",
        "grade_id_snapshot": "Série no momento da participação (imutável após preenchido).",
        "enrollment_id_snapshot": (
            "Matrícula vigente (student_school_enrollment) no momento do resultado."
        ),
    },
}


def _city_schemas_with_table(conn, table_name: str):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = :table AND table_schema LIKE 'city_%' "
            "ORDER BY table_schema"
        ),
        {"table": table_name},
    )
    return [row[0] for row in rows]


def _apply_snapshot_columns(conn, schema: str, table: str) -> None:
    for col, col_type in _SNAPSHOT_COLS:
        conn.execute(
            sa.text(
                f'ALTER TABLE "{schema}".{table} '
                f"ADD COLUMN IF NOT EXISTS {col} {col_type}"
            )
        )
        comment = _COMMENTS[table][col].replace("'", "''")
        conn.execute(
            sa.text(
                f"COMMENT ON COLUMN \"{schema}\".{table}.{col} IS '{comment}'"
            )
        )


def upgrade():
    conn = op.get_bind()
    for schema in _city_schemas_with_table(conn, "answer_sheet_results"):
        _apply_snapshot_columns(conn, schema, "answer_sheet_results")
    for schema in _city_schemas_with_table(conn, "evaluation_results"):
        _apply_snapshot_columns(conn, schema, "evaluation_results")


def downgrade():
    conn = op.get_bind()
    for table in ("answer_sheet_results", "evaluation_results"):
        for schema in _city_schemas_with_table(conn, table):
            for col, _ in _SNAPSHOT_COLS:
                conn.execute(
                    sa.text(
                        f'ALTER TABLE "{schema}".{table} '
                        f"DROP COLUMN IF EXISTS {col}"
                    )
                )
