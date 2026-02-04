"""Fix expected_tasks to be nullable and add batch_id

Revision ID: 20260203_fix_expected_tasks
Revises: f1e2d3c4b5a6
Create Date: 2026-02-03 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260203_fix_expected_tasks'
down_revision = 'f1e2d3c4b5a6'  # merge_heads_coins_and_grade_scope
branch_labels = None
depends_on = None


def _column_exists(connection, table, column):
    """Retorna True se a coluna existir na tabela (PostgreSQL)."""
    r = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return r.scalar() is not None


def upgrade():
    connection = op.get_bind()

    # 1. Tornar expected_tasks NULLABLE se existir
    if _column_exists(connection, 'answer_sheet_gabaritos', 'expected_tasks'):
        with op.batch_alter_table('answer_sheet_gabaritos', schema=None) as batch_op:
            batch_op.alter_column(
                'expected_tasks',
                existing_type=sa.Integer(),
                nullable=True,
            )

    # 2. Tornar completed_tasks NULLABLE se existir
    if _column_exists(connection, 'answer_sheet_gabaritos', 'completed_tasks'):
        with op.batch_alter_table('answer_sheet_gabaritos', schema=None) as batch_op:
            batch_op.alter_column(
                'completed_tasks',
                existing_type=sa.Integer(),
                nullable=True,
            )

    # 3. Adicionar batch_id se ainda não existir
    if not _column_exists(connection, 'answer_sheet_gabaritos', 'batch_id'):
        with op.batch_alter_table('answer_sheet_gabaritos', schema=None) as batch_op:
            batch_op.add_column(sa.Column('batch_id', sa.String(36), nullable=True))


def downgrade():
    connection = op.get_bind()
    if _column_exists(connection, 'answer_sheet_gabaritos', 'batch_id'):
        with op.batch_alter_table('answer_sheet_gabaritos', schema=None) as batch_op:
            batch_op.drop_column('batch_id')
