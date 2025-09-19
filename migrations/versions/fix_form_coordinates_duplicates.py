"""Fix form_coordinates duplicates and add form_type

Revision ID: fix_form_coordinates_duplicates
Revises: b576007eadf8
Create Date: 2025-01-18 10:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_form_coordinates_duplicates'
down_revision = 'b576007eadf8'
branch_labels = None
depends_on = None


def upgrade():
    """Fix duplicates and add form_type"""
    # 1. Primeiro, adicionar coluna form_type com valor padrão
    op.add_column('form_coordinates', sa.Column('form_type', sa.String(50), nullable=True))
    
    # 2. Atualizar registros existentes para ter form_type = 'physical_test'
    op.execute("UPDATE form_coordinates SET form_type = 'physical_test' WHERE form_type IS NULL")
    
    # 3. Tornar form_type NOT NULL
    op.alter_column('form_coordinates', 'form_type', nullable=False)
    
    # 4. Tornar qr_code_id e student_id nullable
    op.alter_column('form_coordinates', 'qr_code_id', nullable=True)
    op.alter_column('form_coordinates', 'student_id', nullable=True)
    
    # 5. Remover constraint único antigo em qr_code_id
    try:
        op.drop_constraint('form_coordinates_qr_code_id_key', 'form_coordinates', type_='unique')
    except:
        pass  # Pode não existir
    
    # 6. Remover duplicados mantendo apenas o primeiro registro de cada (test_id, form_type)
    op.execute("""
        DELETE FROM form_coordinates 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM form_coordinates 
            GROUP BY test_id, form_type
        )
    """)
    
    # 7. Adicionar novo constraint único
    op.create_unique_constraint('unique_test_form_type', 'form_coordinates', ['test_id', 'form_type'])


def downgrade():
    """Revert changes"""
    # Remover novo constraint
    op.drop_constraint('unique_test_form_type', 'form_coordinates', type_='unique')
    
    # Restaurar constraint antigo
    op.create_unique_constraint('form_coordinates_qr_code_id_key', 'form_coordinates', ['qr_code_id'])
    
    # Tornar campos NOT NULL novamente
    op.alter_column('form_coordinates', 'student_id', nullable=False)
    op.alter_column('form_coordinates', 'qr_code_id', nullable=False)
    
    # Remover coluna form_type
    op.drop_column('form_coordinates', 'form_type')
