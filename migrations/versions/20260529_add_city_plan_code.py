# -*- coding: utf-8 -*-
"""Add plan_code to public.city (basic | plus)

Municípios existentes recebem plano basic (comportamento atual do produto).
Plus reserva features futuras; enforcement fica na aplicação (próximos passos).

Revision ID: add_city_plan_code
Revises: add_mobile_city_directory
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = "add_city_plan_code"
down_revision = "add_mobile_city_directory"
branch_labels = None
depends_on = None

_PLAN_CHECK = "plan_code IN ('basic', 'plus')"


def upgrade():
    op.add_column(
        "city",
        sa.Column(
            "plan_code",
            sa.String(20),
            nullable=False,
            server_default="basic",
        ),
        schema="public",
    )
    op.create_check_constraint(
        "ck_city_plan_code",
        "city",
        _PLAN_CHECK,
        schema="public",
    )
    # Garantir linhas legadas (redundante com server_default, explícito para clareza)
    op.execute(sa.text("UPDATE public.city SET plan_code = 'basic' WHERE plan_code IS NULL"))


def downgrade():
    op.drop_constraint("ck_city_plan_code", "city", type_="check", schema="public")
    op.drop_column("city", "plan_code", schema="public")
