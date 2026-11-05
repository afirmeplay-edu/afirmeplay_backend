# -*- coding: utf-8 -*-
"""Tabelas de certificados de formação continuada nos schemas city_%.

Revision ID: 20261105_formation_certs
Revises: 20261105_dictation_marks
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa


revision = "20261105_formation_certs"
down_revision = "20261105_dictation_marks"
branch_labels = None
depends_on = None


def _city_schemas_with_school(conn):
    rows = conn.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'school' AND table_schema LIKE 'city_%' "
            "ORDER BY table_schema"
        )
    )
    return [row[0] for row in rows]


def _safe_city_schema(schema: str) -> str:
    if not schema.startswith("city_") or not schema.replace("_", "").isalnum():
        raise ValueError(f"Nome de schema inválido: {schema}")
    return schema


def _create_sql(schema: str) -> str:
    schema = _safe_city_schema(schema)
    return f"""
CREATE TABLE IF NOT EXISTS "{schema}".formation_certificate_events (
    id VARCHAR NOT NULL,
    title VARCHAR(255) NOT NULL,
    trainer VARCHAR(255) NOT NULL,
    audience VARCHAR(255) NOT NULL,
    subtitle TEXT,
    certificate_text TEXT NOT NULL,
    year VARCHAR(20) NOT NULL,
    issued_text VARCHAR(120),
    signer_role VARCHAR(255),
    signature_url VARCHAR(500),
    verify_url VARCHAR(500),
    topics JSON NOT NULL,
    municipality_id VARCHAR,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (created_by) REFERENCES public.users (id)
);
CREATE TABLE IF NOT EXISTS "{schema}".formation_certificate_participants (
    id VARCHAR NOT NULL,
    event_id VARCHAR NOT NULL,
    name VARCHAR(255) NOT NULL,
    external_ref VARCHAR(120),
    user_id VARCHAR,
    certificate_code VARCHAR(64) NOT NULL,
    issued_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_formation_cert_code UNIQUE (event_id, certificate_code),
    FOREIGN KEY (event_id) REFERENCES "{schema}".formation_certificate_events (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES public.users (id)
);
CREATE INDEX IF NOT EXISTS ix_formation_cert_participants_event
    ON "{schema}".formation_certificate_participants (event_id);
CREATE INDEX IF NOT EXISTS ix_formation_cert_participants_code
    ON "{schema}".formation_certificate_participants (certificate_code);
"""


def upgrade():
    bind = op.get_bind()
    for schema in _city_schemas_with_school(bind):
        bind.execute(sa.text(_create_sql(schema)))


def downgrade():
    bind = op.get_bind()
    for schema in _city_schemas_with_school(bind):
        schema = _safe_city_schema(schema)
        bind.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".formation_certificate_participants'))
        bind.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".formation_certificate_events'))
