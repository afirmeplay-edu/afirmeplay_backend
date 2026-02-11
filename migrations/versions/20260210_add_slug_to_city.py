"""Add slug to city table

Revision ID: 20260210_add_slug_to_city
Revises: 
Create Date: 2026-02-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '20260210_add_slug_to_city'
down_revision = None  # Altere para apontar para a última migração
branch_labels = None
depends_on = None


def upgrade():
    """
    Adiciona o campo slug à tabela city.
    O slug será usado para resolução de schema baseada em subdomínio.
    """
    # Adicionar coluna slug à tabela city
    op.add_column('city', sa.Column('slug', sa.String(100), nullable=True))
    
    # Criar índice único no slug
    op.create_unique_constraint('uq_city_slug', 'city', ['slug'])
    
    # Popular slugs com base no name (converter para lowercase e substituir espaços)
    # Esta operação será feita manualmente após a migração para garantir slugs corretos
    connection = op.get_bind()
    connection.execute(text("""
        UPDATE city 
        SET slug = LOWER(REGEXP_REPLACE(name, '[^a-zA-Z0-9]', '', 'g'))
        WHERE slug IS NULL
    """))
    
    # Tornar slug obrigatório após popular
    op.alter_column('city', 'slug', nullable=False)


def downgrade():
    """
    Remove o campo slug da tabela city.
    """
    op.drop_constraint('uq_city_slug', 'city', type_='unique')
    op.drop_column('city', 'slug')
