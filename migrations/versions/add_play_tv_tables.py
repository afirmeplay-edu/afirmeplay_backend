"""Add play_tv_videos, play_tv_video_schools and play_tv_video_classes tables

Revision ID: add_play_tv_tables
Revises: 75a6b30782f9
Create Date: 2025-01-XX 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_play_tv_tables'
down_revision = '75a6b30782f9'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela play_tv_videos
    op.create_table('play_tv_videos',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=True),
        sa.Column('grade_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subject_id', sa.String(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['grade_id'], ['grade.id'], ),
        sa.ForeignKeyConstraint(['subject_id'], ['subject.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Criar índices para play_tv_videos
    op.create_index(op.f('ix_play_tv_videos_grade_id'), 'play_tv_videos', ['grade_id'], unique=False)
    op.create_index(op.f('ix_play_tv_videos_subject_id'), 'play_tv_videos', ['subject_id'], unique=False)
    op.create_index(op.f('ix_play_tv_videos_created_by'), 'play_tv_videos', ['created_by'], unique=False)
    
    # Criar tabela play_tv_video_schools
    op.create_table('play_tv_video_schools',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('video_id', sa.String(), nullable=False),
        sa.Column('school_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['video_id'], ['play_tv_videos.id'], ),
        sa.ForeignKeyConstraint(['school_id'], ['school.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id', 'school_id', name='uq_play_tv_video_school')
    )
    
    # Criar índices para play_tv_video_schools
    op.create_index(op.f('ix_play_tv_video_schools_video_id'), 'play_tv_video_schools', ['video_id'], unique=False)
    op.create_index(op.f('ix_play_tv_video_schools_school_id'), 'play_tv_video_schools', ['school_id'], unique=False)
    
    # Criar tabela play_tv_video_classes
    op.create_table('play_tv_video_classes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('video_id', sa.String(), nullable=False),
        sa.Column('class_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['video_id'], ['play_tv_videos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['class.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id', 'class_id', name='uq_play_tv_video_class')
    )
    
    # Criar índices para play_tv_video_classes
    op.create_index(op.f('ix_play_tv_video_classes_video_id'), 'play_tv_video_classes', ['video_id'], unique=False)
    op.create_index(op.f('ix_play_tv_video_classes_class_id'), 'play_tv_video_classes', ['class_id'], unique=False)


def downgrade():
    # Remover índices
    op.drop_index(op.f('ix_play_tv_video_classes_class_id'), table_name='play_tv_video_classes')
    op.drop_index(op.f('ix_play_tv_video_classes_video_id'), table_name='play_tv_video_classes')
    op.drop_index(op.f('ix_play_tv_video_schools_school_id'), table_name='play_tv_video_schools')
    op.drop_index(op.f('ix_play_tv_video_schools_video_id'), table_name='play_tv_video_schools')
    op.drop_index(op.f('ix_play_tv_videos_created_by'), table_name='play_tv_videos')
    op.drop_index(op.f('ix_play_tv_videos_subject_id'), table_name='play_tv_videos')
    op.drop_index(op.f('ix_play_tv_videos_grade_id'), table_name='play_tv_videos')
    
    # Remover tabelas
    op.drop_table('play_tv_video_classes')
    op.drop_table('play_tv_video_schools')
    op.drop_table('play_tv_videos')



