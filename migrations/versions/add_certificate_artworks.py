"""Add optional certificate artwork models.

Revision ID: add_certificate_artworks
Revises: add_certificates_tables
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_certificate_artworks'
down_revision = 'add_certificates_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'certificate_artworks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('evaluation_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('source_kind', sa.String(length=20), nullable=False),
        sa.Column('minio_bucket', sa.String(length=100), nullable=False),
        sa.Column('minio_object_name', sa.String(length=500), nullable=False),
        sa.Column('normalized_object_name', sa.String(length=500), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('page_width_pt', sa.Float(), nullable=False),
        sa.Column('page_height_pt', sa.Float(), nullable=False),
        sa.Column('rotation', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fields', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['evaluation_id'], ['test.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_certificate_artworks_evaluation_status', 'certificate_artworks', ['evaluation_id', 'status'])


def downgrade():
    op.drop_index('idx_certificate_artworks_evaluation_status', table_name='certificate_artworks')
    op.drop_table('certificate_artworks')
