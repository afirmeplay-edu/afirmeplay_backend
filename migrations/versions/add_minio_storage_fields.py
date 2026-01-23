"""add_minio_storage_fields

Revision ID: add_minio_storage
Revises: 
Create Date: 2026-01-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_minio_storage'
down_revision = 'add_template_base_image'  # Mesmo nível que as outras heads
branch_labels = None
depends_on = None


def upgrade():
    """
    Adiciona campos para armazenamento MinIO nos modelos:
    - AnswerSheetGabarito
    - PhysicalTestForm
    """
    # AnswerSheetGabarito - campos MinIO
    op.add_column('answer_sheet_gabarito', 
        sa.Column('minio_url', sa.String(500), nullable=True))
    op.add_column('answer_sheet_gabarito', 
        sa.Column('minio_object_name', sa.String(200), nullable=True))
    op.add_column('answer_sheet_gabarito', 
        sa.Column('minio_bucket', sa.String(100), nullable=True))
    op.add_column('answer_sheet_gabarito', 
        sa.Column('zip_generated_at', sa.DateTime(), nullable=True))
    
    # PhysicalTestForm - campos MinIO
    op.add_column('physical_test_form', 
        sa.Column('minio_url', sa.String(500), nullable=True))
    op.add_column('physical_test_form', 
        sa.Column('minio_object_name', sa.String(200), nullable=True))
    op.add_column('physical_test_form', 
        sa.Column('minio_bucket', sa.String(100), nullable=True))


def downgrade():
    """
    Remove campos MinIO
    """
    # AnswerSheetGabarito
    op.drop_column('answer_sheet_gabarito', 'zip_generated_at')
    op.drop_column('answer_sheet_gabarito', 'minio_bucket')
    op.drop_column('answer_sheet_gabarito', 'minio_object_name')
    op.drop_column('answer_sheet_gabarito', 'minio_url')
    
    # PhysicalTestForm
    op.drop_column('physical_test_form', 'minio_bucket')
    op.drop_column('physical_test_form', 'minio_object_name')
    op.drop_column('physical_test_form', 'minio_url')
