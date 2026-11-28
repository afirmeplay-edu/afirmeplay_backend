# -*- coding: utf-8 -*-
"""Tabela tenant answer_sheet_identity_codes (token OMR 6 hex ↔ aluno+doc).

Revision ID: 20261127_identity_codes
Revises: 20261106_logistics_sources
Create Date: 2026-11-27
"""
from alembic import op
import sqlalchemy as sa


revision = "20261127_identity_codes"
down_revision = "20261106_logistics_sources"
branch_labels = None
depends_on = None


DDL = """
CREATE TABLE IF NOT EXISTS "{schema}".answer_sheet_identity_codes (
    id VARCHAR PRIMARY KEY,
    code CHAR(6) NOT NULL,
    kind CHAR(1) NOT NULL,
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    gabarito_id VARCHAR REFERENCES "{schema}".answer_sheet_gabaritos(id),
    test_id VARCHAR REFERENCES "{schema}".test(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT asic_kind_doc_check CHECK (
        (kind = '1' AND gabarito_id IS NOT NULL AND test_id IS NULL)
        OR (kind = '2' AND test_id IS NOT NULL AND gabarito_id IS NULL)
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_asic_code
    ON "{schema}".answer_sheet_identity_codes(code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_asic_student_gabarito
    ON "{schema}".answer_sheet_identity_codes(student_id, gabarito_id)
    WHERE gabarito_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_asic_student_test
    ON "{schema}".answer_sheet_identity_codes(student_id, test_id)
    WHERE test_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_asic_student
    ON "{schema}".answer_sheet_identity_codes(student_id);
COMMENT ON TABLE "{schema}".answer_sheet_identity_codes IS
    'Token OMR ID-Grid (6 hex) 1:1:1 aluno + gabarito ou prova';
"""


def _city_schemas_with_student(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'student' "
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
    bind = op.get_bind()
    for schema in _city_schemas_with_student(bind):
        schema = _safe_city_schema(schema)
        bind.execute(sa.text(DDL.format(schema=schema)))


def downgrade():
    bind = op.get_bind()
    for schema in _city_schemas_with_student(bind):
        schema = _safe_city_schema(schema)
        bind.execute(
            sa.text(
                f'DROP TABLE IF EXISTS "{schema}".answer_sheet_identity_codes CASCADE'
            )
        )
