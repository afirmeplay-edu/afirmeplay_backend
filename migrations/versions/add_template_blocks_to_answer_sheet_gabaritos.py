"""Add template_block_1 to template_block_4 fields to answer_sheet_gabaritos

Template Real Digital: Armazena imagens PNG dos blocos de questões
gerados pelo MESMO pipeline de correção do aluno.
Isso elimina desalinhamento por DPI, escala e geometria.

Revision ID: add_template_blocks
Revises: add_template_base_image
Create Date: 2026-01-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_template_blocks'
down_revision = 'add_template_base_image'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar colunas de template de blocos (LargeBinary - PNG bytes diretos)
    # Cada bloco é salvo separadamente para facilitar acesso e evitar serialização JSON
    
    op.add_column('answer_sheet_gabaritos',
        sa.Column('template_block_1', sa.LargeBinary(), nullable=True,
                  comment='PNG bytes do bloco 1 (gerado pelo mesmo pipeline de correção)')
    )
    
    op.add_column('answer_sheet_gabaritos',
        sa.Column('template_block_2', sa.LargeBinary(), nullable=True,
                  comment='PNG bytes do bloco 2 (gerado pelo mesmo pipeline de correção)')
    )
    
    op.add_column('answer_sheet_gabaritos',
        sa.Column('template_block_3', sa.LargeBinary(), nullable=True,
                  comment='PNG bytes do bloco 3 (gerado pelo mesmo pipeline de correção)')
    )
    
    op.add_column('answer_sheet_gabaritos',
        sa.Column('template_block_4', sa.LargeBinary(), nullable=True,
                  comment='PNG bytes do bloco 4 (gerado pelo mesmo pipeline de correção)')
    )
    
    # Metadados dos templates
    op.add_column('answer_sheet_gabaritos',
        sa.Column('template_generated_at', sa.TIMESTAMP(), nullable=True,
                  comment='Data/hora de geração dos templates')
    )
    
    op.add_column('answer_sheet_gabaritos',
        sa.Column('template_dpi', sa.Integer(), nullable=True,
                  comment='DPI usado na renderização do PDF (ex: 300)')
    )


def downgrade():
    # Remover colunas em ordem inversa
    op.drop_column('answer_sheet_gabaritos', 'template_dpi')
    op.drop_column('answer_sheet_gabaritos', 'template_generated_at')
    op.drop_column('answer_sheet_gabaritos', 'template_block_4')
    op.drop_column('answer_sheet_gabaritos', 'template_block_3')
    op.drop_column('answer_sheet_gabaritos', 'template_block_2')
    op.drop_column('answer_sheet_gabaritos', 'template_block_1')
