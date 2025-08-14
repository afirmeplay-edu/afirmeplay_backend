"""Add timezone column to class_test table

Revision ID: add_timezone_to_class_test
Revises: 48b50f609011
Create Date: 2025-08-14 13:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_timezone_to_class_test'
down_revision = '48b50f609011'
branch_labels = None
depends_on = None


def upgrade():
    """Add timezone column to class_test table"""
    with op.batch_alter_table('class_test', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timezone', sa.String(50), nullable=True))
        
        # Adicionar comentário para documentar o campo
        batch_op.alter_column('timezone',
                             comment='Timezone da aplicação da avaliação (ex: America/Sao_Paulo)',
                             existing_type=sa.String(50),
                             existing_nullable=True)


def downgrade():
    """Remove timezone column from class_test table"""
    with op.batch_alter_table('class_test', schema=None) as batch_op:
        batch_op.drop_column('timezone')
