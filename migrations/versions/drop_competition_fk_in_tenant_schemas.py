# -*- coding: utf-8 -*-
"""Remove FK de competition_id em competition_enrollments, competition_results e competition_rewards nos schemas tenant.

Permite inscrever alunos em competições que estão em public.competitions (escopo individual);
enrollments/results/rewards ficam no tenant e passam a armazenar competition_id sem FK no banco.
"""
from alembic import op
import sqlalchemy as sa
import logging

log = logging.getLogger(__name__)

revision = 'drop_competition_fk_tenant'
down_revision = 'recreate_competitions_public'
branch_labels = None
depends_on = None

# Nomes das constraints FK no PostgreSQL (padrão: tablename_columnname_fkey)
CONSTRAINTS = [
    ('competition_enrollments', 'competition_enrollments_competition_id_fkey'),
    ('competition_results', 'competition_results_competition_id_fkey'),
    ('competition_rewards', 'competition_rewards_competition_id_fkey'),
]


def upgrade():
    conn = op.get_bind()
    # Schemas onde competition_enrollments existe (city_xxx e eventualmente public)
    r = conn.execute(sa.text(
        "SELECT DISTINCT table_schema FROM information_schema.tables "
        "WHERE table_name = 'competition_enrollments'"
    ))
    schemas = [row[0] for row in r]
    for schema in schemas:
        for table_name, constraint_name in CONSTRAINTS:
            try:
                conn.execute(sa.text(
                    f'ALTER TABLE "{schema}"."{table_name}" '
                    f'DROP CONSTRAINT IF EXISTS "{constraint_name}"'
                ))
                log.info("Dropped %s.%s constraint %s", schema, table_name, constraint_name)
            except Exception as e:
                log.warning(
                    "drop_competition_fk_tenant: schema=%s table=%s constraint=%s: %s",
                    schema, table_name, constraint_name, e,
                )


def downgrade():
    # Não recriamos as FKs no downgrade: as tabelas em tenant referenciariam
    # apenas competitions no mesmo schema; competições em public continuariam
    # quebrando a FK. Deixar sem FK é o estado desejado.
    pass
