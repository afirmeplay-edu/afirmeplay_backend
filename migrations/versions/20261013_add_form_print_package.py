# -*- coding: utf-8 -*-
"""Último pacote impresso em forms (city_%).

Guarda status, contagens e o objeto do ZIP. A URL só muda depois do upload.
Idempotente (ADD COLUMN IF NOT EXISTS).

Revision ID: 20261013_form_print_package
Revises: merge_estimated_time_notifications
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa


revision = "20261013_form_print_package"
down_revision = "merge_estimated_time_notifications"
branch_labels = None
depends_on = None

_PRINT_COLS = (
    ("print_status", "VARCHAR(20)"),
    ("print_task_id", "VARCHAR(64)"),
    ("print_run_id", "VARCHAR(36)"),
    ("print_zip_bucket", "VARCHAR(100)"),
    ("print_zip_object_name", "VARCHAR(500)"),
    ("print_zip_url", "TEXT"),
    ("print_student_count", "INTEGER"),
    ("print_generated_count", "INTEGER"),
    ("print_failed_count", "INTEGER"),
    ("print_cover_year", "INTEGER"),
    ("print_error", "TEXT"),
    ("print_started_at", "TIMESTAMP"),
    ("print_finished_at", "TIMESTAMP"),
)


def _city_schemas_with_forms(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'forms' AND table_schema LIKE 'city_%' "
            "ORDER BY table_schema"
        )
    )
    return [row[0] for row in rows]


def upgrade():
    conn = op.get_bind()
    for schema in _city_schemas_with_forms(conn):
        for col, col_type in _PRINT_COLS:
            conn.execute(
                sa.text(
                    f'ALTER TABLE "{schema}".forms '
                    f"ADD COLUMN IF NOT EXISTS {col} {col_type}"
                )
            )
        conn.execute(
            sa.text(
                f"COMMENT ON COLUMN \"{schema}\".forms.print_status IS "
                "'processing, completed ou failed. completed só depois do upload do ZIP.'"
            )
        )


def downgrade():
    conn = op.get_bind()
    for schema in _city_schemas_with_forms(conn):
        for col, _col_type in reversed(_PRINT_COLS):
            conn.execute(
                sa.text(f'ALTER TABLE "{schema}".forms DROP COLUMN IF EXISTS {col}')
            )
