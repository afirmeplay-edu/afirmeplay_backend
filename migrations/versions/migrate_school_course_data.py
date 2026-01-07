"""Migrate existing data to school_course table

Revision ID: migrate_school_course_data
Revises: add_school_course
Create Date: 2024-01-20 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'migrate_school_course_data'
down_revision = 'add_school_course'
branch_labels = None
depends_on = None


def upgrade():
    """
    Migra dados existentes para a tabela school_course.
    
    Para cada turma (Class) existente:
    - Busca o grade_id da turma
    - Busca o education_stage_id do grade
    - Cria registro em school_course se não existir
    """
    connection = op.get_bind()
    
    # SQL para migrar dados
    # Insere cursos na tabela school_course baseado nas turmas existentes
    # Usa ON CONFLICT DO NOTHING para evitar erros de duplicata
    migration_sql = text("""
        INSERT INTO school_course (id, school_id, education_stage_id, created_at)
        SELECT DISTINCT
            gen_random_uuid() as id,
            c.school_id,
            g.education_stage_id,
            CURRENT_TIMESTAMP as created_at
        FROM class c
        INNER JOIN grade g ON c.grade_id = g.id
        WHERE c.school_id IS NOT NULL
          AND g.education_stage_id IS NOT NULL
        ON CONFLICT (school_id, education_stage_id) DO NOTHING
    """)
    
    try:
        connection.execute(migration_sql)
        connection.commit()
        print("Migration completed successfully: school_course data migrated")
    except Exception as e:
        connection.rollback()
        print(f"Migration error: {str(e)}")
        raise


def downgrade():
    """
    Não há downgrade para migration de dados.
    Os dados migrados serão mantidos mesmo se a tabela for removida.
    """
    pass

