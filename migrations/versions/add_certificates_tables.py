"""Add certificate_templates and certificates tables

Revision ID: add_certificates_tables
Revises: add_template_base_image
Create Date: 2025-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_certificates_tables'
down_revision = 'add_template_base_image'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela certificate_templates
    op.create_table('certificate_templates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('evaluation_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('text_content', sa.Text(), nullable=False),
        sa.Column('background_color', sa.String(length=7), nullable=False),
        sa.Column('text_color', sa.String(length=7), nullable=False),
        sa.Column('accent_color', sa.String(length=7), nullable=False),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('signature_url', sa.String(length=500), nullable=True),
        sa.Column('custom_date', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['evaluation_id'], ['test.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('evaluation_id', name='uq_certificate_template_evaluation')
    )
    
    # Índices para certificate_templates
    op.create_index(op.f('ix_certificate_templates_evaluation_id'), 'certificate_templates', ['evaluation_id'], unique=False)
    
    # Criar tabela certificates
    op.create_table('certificates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('student_name', sa.String(length=200), nullable=False),
        sa.Column('evaluation_id', sa.String(), nullable=False),
        sa.Column('evaluation_title', sa.String(length=200), nullable=False),
        sa.Column('grade', sa.Float(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('issued_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['student.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evaluation_id'], ['test.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['certificate_templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'evaluation_id', name='uq_certificate_student_evaluation')
    )
    
    # Índices para certificates
    op.create_index(op.f('ix_certificates_student_id'), 'certificates', ['student_id'], unique=False)
    op.create_index(op.f('ix_certificates_evaluation_id'), 'certificates', ['evaluation_id'], unique=False)
    op.create_index(op.f('ix_certificates_template_id'), 'certificates', ['template_id'], unique=False)
    op.create_index(op.f('ix_certificates_status'), 'certificates', ['status'], unique=False)
    op.create_index(op.f('ix_certificates_issued_at'), 'certificates', ['issued_at'], unique=False)


def downgrade():
    # Remover índices de certificates
    op.drop_index(op.f('ix_certificates_issued_at'), table_name='certificates')
    op.drop_index(op.f('ix_certificates_status'), table_name='certificates')
    op.drop_index(op.f('ix_certificates_template_id'), table_name='certificates')
    op.drop_index(op.f('ix_certificates_evaluation_id'), table_name='certificates')
    op.drop_index(op.f('ix_certificates_student_id'), table_name='certificates')
    
    # Remover tabela certificates
    op.drop_table('certificates')
    
    # Remover índices de certificate_templates
    op.drop_index(op.f('ix_certificate_templates_evaluation_id'), table_name='certificate_templates')
    
    # Remover tabela certificate_templates
    op.drop_table('certificate_templates')
