"""add ai analysis to report aggregates

Revision ID: a1b2c3d4e5f6
Revises: 966ab4061d7b
Create Date: 2025-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '966ab4061d7b'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar colunas para análise de IA
    op.add_column('report_aggregates', sa.Column('ai_analysis', sa.JSON(), nullable=True, server_default=sa.text("'{}'::json")))
    op.add_column('report_aggregates', sa.Column('ai_analysis_generated_at', sa.DateTime(), nullable=True))
    op.add_column('report_aggregates', sa.Column('ai_analysis_is_dirty', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade():
    op.drop_column('report_aggregates', 'ai_analysis_is_dirty')
    op.drop_column('report_aggregates', 'ai_analysis_generated_at')
    op.drop_column('report_aggregates', 'ai_analysis')

