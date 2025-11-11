"""add report aggregates table

Revision ID: 1a2b3c4d5e6f
Revises: 0fe0422f58b0
Create Date: 2025-11-11 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = '0fe0422f58b0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'report_aggregates',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('test_id', sa.String(), sa.ForeignKey('test.id'), nullable=False),
        sa.Column('scope_type', sa.String(length=32), nullable=False),
        sa.Column('scope_id', sa.String(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column('student_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('generated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('is_dirty', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.create_index('ix_report_aggregates_test_id', 'report_aggregates', ['test_id'])
    op.create_index('ix_report_aggregates_scope_type', 'report_aggregates', ['scope_type'])
    op.create_index('ix_report_aggregates_scope_id', 'report_aggregates', ['scope_id'])
    op.create_unique_constraint(
        'uq_report_aggregate_scope',
        'report_aggregates',
        ['test_id', 'scope_type', 'scope_id'],
    )


def downgrade():
    op.drop_constraint('uq_report_aggregate_scope', 'report_aggregates', type_='unique')
    op.drop_index('ix_report_aggregates_scope_id', table_name='report_aggregates')
    op.drop_index('ix_report_aggregates_scope_type', table_name='report_aggregates')
    op.drop_index('ix_report_aggregates_test_id', table_name='report_aggregates')
    op.drop_table('report_aggregates')


