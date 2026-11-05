# -*- coding: utf-8 -*-
"""Tabelas de certificados de formação continuada (tenant).

Revision ID: 20261105_formation_certs
Revises: 20261105_dictation_marks
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261105_formation_certs"
down_revision = "20261105_dictation_marks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "formation_certificate_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("trainer", sa.String(length=255), nullable=False),
        sa.Column("audience", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("certificate_text", sa.Text(), nullable=False),
        sa.Column("year", sa.String(length=20), nullable=False),
        sa.Column("issued_text", sa.String(length=120), nullable=True),
        sa.Column("signer_role", sa.String(length=255), nullable=True),
        sa.Column("signature_url", sa.String(length=500), nullable=True),
        sa.Column("verify_url", sa.String(length=500), nullable=True),
        sa.Column("topics", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("municipality_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="tenant",
    )
    op.create_table(
        "formation_certificate_participants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("external_ref", sa.String(length=120), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("certificate_code", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["tenant.formation_certificate_events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "certificate_code", name="uq_formation_cert_code"),
        schema="tenant",
    )
    op.create_index(
        "ix_formation_cert_participants_event",
        "formation_certificate_participants",
        ["event_id"],
        unique=False,
        schema="tenant",
    )
    op.create_index(
        "ix_formation_cert_participants_code",
        "formation_certificate_participants",
        ["certificate_code"],
        unique=False,
        schema="tenant",
    )


def downgrade():
    op.drop_index(
        "ix_formation_cert_participants_code",
        table_name="formation_certificate_participants",
        schema="tenant",
    )
    op.drop_index(
        "ix_formation_cert_participants_event",
        table_name="formation_certificate_participants",
        schema="tenant",
    )
    op.drop_table("formation_certificate_participants", schema="tenant")
    op.drop_table("formation_certificate_events", schema="tenant")
