"""Add game_classes table

Revision ID: add_game_classes_table
Revises: add_play_tv_tables
Create Date: 2025-01-XX 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_game_classes_table'
down_revision = 'add_play_tv_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela game_classes
    op.create_table('game_classes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('game_id', sa.String(), nullable=False),
        sa.Column('class_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['class.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'class_id', name='uq_game_class')
    )
    
    # Criar índices para game_classes
    op.create_index(op.f('ix_game_classes_game_id'), 'game_classes', ['game_id'], unique=False)
    op.create_index(op.f('ix_game_classes_class_id'), 'game_classes', ['class_id'], unique=False)


def downgrade():
    # Remover índices
    op.drop_index(op.f('ix_game_classes_class_id'), table_name='game_classes')
    op.drop_index(op.f('ix_game_classes_game_id'), table_name='game_classes')
    
    # Remover tabela
    op.drop_table('game_classes')

