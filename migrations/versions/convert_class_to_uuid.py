"""Convert class.id and class.school_id to UUID

Revision ID: convert_class_to_uuid
Revises: add_filters_selected_classes_forms
Create Date: 2025-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'convert_class_to_uuid'
down_revision = 'add_filters_selected_classes_forms'
branch_labels = None
depends_on = None


def upgrade():
    """
    Converte class.id e class.school_id de VARCHAR para UUID
    
    ORDEM OBRIGATÓRIA:
    1. Remover todas as FKs que referenciam class.id
    2. Converter todas as colunas filhas (class_id)
    3. Converter coluna pai (class.id)
    4. Recriar todas as FKs
    5. Repetir para class.school_id (se necessário)
    """
    connection = op.get_bind()
    
    # Lista de tabelas e colunas que referenciam class.id
    tables_with_class_id = [
        ('class_test', 'class_id'),
        ('teacher_class', 'class_id'),
        ('student', 'class_id'),
        ('answer_sheet_gabaritos', 'class_id'),
        ('student_password_log', 'class_id'),
        ('calendar_event_users', 'class_id'),  # Note: plural no banco
        ('game_classes', 'class_id'),
        ('class_subject', 'class_id'),
        ('play_tv_video_classes', 'class_id'),  # Tabela do PlayTV
    ]
    
    # ============================================
    # PARTE 1: Converter class.id e suas FKs
    # ============================================
    
    # 1.1 Remover TODAS as foreign keys que referenciam class.id
    print("Removendo foreign keys que referenciam class.id...")
    for table_name, column_name in tables_with_class_id:
        # Verificar se a tabela existe
        result = connection.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{table_name}'
            );
        """))
        
        if not result.scalar():
            print(f"  Tabela {table_name} não existe, pulando...")
            continue
        
        # Verificar se a coluna existe
        result = connection.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = '{table_name}' 
                AND column_name = '{column_name}'
            );
        """))
        
        if not result.scalar():
            print(f"  Coluna {table_name}.{column_name} não existe, pulando...")
            continue
        
        # Encontrar e remover a foreign key constraint
        op.execute(text(f"""
            DO $$
            DECLARE
                fk_name TEXT;
            BEGIN
                -- Encontrar o nome da constraint de foreign key
                SELECT tc.constraint_name INTO fk_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.table_name = '{table_name}'
                AND tc.constraint_type = 'FOREIGN KEY'
                AND kcu.column_name = '{column_name}'
                AND tc.table_schema = 'public'
                LIMIT 1;
                
                IF fk_name IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I', '{table_name}', fk_name);
                    RAISE NOTICE 'Removida FK: %', fk_name;
                END IF;
            END $$;
        """))
    
    # 1.2 Converter TODAS as colunas filhas (class_id) para UUID
    print("Convertendo colunas filhas (class_id) para UUID...")
    for table_name, column_name in tables_with_class_id:
        # Verificar se a tabela e coluna existem
        result = connection.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = '{table_name}' 
                AND column_name = '{column_name}'
            );
        """))
        
        if not result.scalar():
            continue
        
        # Verificar se há valores inválidos
        op.execute(text(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM {table_name} 
                    WHERE {column_name} IS NOT NULL 
                    AND {column_name}::text !~ '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$'
                ) THEN
                    RAISE EXCEPTION 'Existem valores inválidos na coluna {table_name}.{column_name} que não são UUIDs válidos';
                END IF;
            END $$;
        """))
        
        # Converter a coluna para UUID
        op.execute(text(f"""
            ALTER TABLE {table_name} 
            ALTER COLUMN {column_name} TYPE UUID USING {column_name}::UUID;
        """))
        print(f"  Convertido {table_name}.{column_name} para UUID")
    
    # 1.3 Converter a coluna PAI (class.id) para UUID
    print("Convertendo coluna pai (class.id) para UUID...")
    op.execute(text("""
        -- Verificar se há valores inválidos
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM class 
                WHERE id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            ) THEN
                RAISE EXCEPTION 'Existem valores inválidos na coluna class.id que não são UUIDs válidos';
            END IF;
        END $$;
    """))
    
    op.execute(text("""
        ALTER TABLE class 
        ALTER COLUMN id TYPE UUID USING id::UUID;
    """))
    print("  Convertido class.id para UUID")
    
    # 1.4 Recriar TODAS as foreign keys
    print("Recriando foreign keys...")
    for table_name, column_name in tables_with_class_id:
        # Verificar se a tabela e coluna existem
        result = connection.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = '{table_name}' 
                AND column_name = '{column_name}'
            );
        """))
        
        if not result.scalar():
            continue
        
        # Recriar foreign key constraint
        op.execute(text(f"""
            ALTER TABLE {table_name}
            ADD CONSTRAINT fk_{table_name}_{column_name}
            FOREIGN KEY ({column_name}) REFERENCES class(id)
            ON DELETE CASCADE;
        """))
        print(f"  Recriada FK: fk_{table_name}_{column_name}")
    
    # ============================================
    # PARTE 2: Converter class.school_id para UUID
    # ============================================
    # NOTA: Assumindo que school.id ainda é VARCHAR
    # Se school.id já for UUID, podemos converter diretamente
    
    print("Convertendo class.school_id para UUID...")
    
    # Verificar se há valores inválidos
    op.execute(text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM class 
                WHERE school_id IS NOT NULL 
                AND school_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            ) THEN
                RAISE EXCEPTION 'Existem valores inválidos na coluna class.school_id que não são UUIDs válidos';
            END IF;
        END $$;
    """))
    
    # Remover FK temporariamente (se existir)
    op.execute(text("""
        DO $$
        DECLARE
            fk_name TEXT;
        BEGIN
            SELECT tc.constraint_name INTO fk_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_name = 'class'
            AND tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name = 'school_id'
            AND tc.table_schema = 'public'
            LIMIT 1;
            
            IF fk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE class DROP CONSTRAINT IF EXISTS %I', fk_name);
                RAISE NOTICE 'Removida FK: %', fk_name;
            END IF;
        END $$;
    """))
    
    # Converter class.school_id para UUID
    op.execute(text("""
        ALTER TABLE class 
        ALTER COLUMN school_id TYPE UUID USING school_id::UUID;
    """))
    print("  Convertido class.school_id para UUID")
    
    # Recriar FK (assumindo que school.id ainda é VARCHAR, então não podemos recriar ainda)
    # Se school.id já for UUID, descomente abaixo:
    # op.execute(text("""
    #     ALTER TABLE class
    #     ADD CONSTRAINT fk_class_school_id
    #     FOREIGN KEY (school_id) REFERENCES school(id)
    #     ON DELETE CASCADE;
    # """))
    
    print("Migration concluída com sucesso!")


def downgrade():
    """
    Reverte class.id e class.school_id de UUID para VARCHAR
    """
    connection = op.get_bind()
    
    # Lista de tabelas e colunas que referenciam class.id
    tables_with_class_id = [
        ('class_test', 'class_id'),
        ('teacher_class', 'class_id'),
        ('student', 'class_id'),
        ('answer_sheet_gabaritos', 'class_id'),
        ('student_password_log', 'class_id'),
        ('calendar_event_users', 'class_id'),
        ('game_classes', 'class_id'),
        ('class_subject', 'class_id'),
        ('play_tv_video_classes', 'class_id'),  # Tabela do PlayTV
    ]
    
    # Reverter class.school_id primeiro (se tiver FK)
    op.execute(text("""
        DO $$
        DECLARE
            fk_name TEXT;
        BEGIN
            SELECT constraint_name INTO fk_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_name = 'class'
            AND tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name = 'school_id'
            AND kcu.table_schema = 'public'
            LIMIT 1;
            
            IF fk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE class DROP CONSTRAINT IF EXISTS %I', fk_name);
            END IF;
        END $$;
    """))
    
    op.execute(text("""
        ALTER TABLE class 
        ALTER COLUMN school_id TYPE VARCHAR USING school_id::VARCHAR;
    """))
    
    # Remover FKs das tabelas filhas
    for table_name, column_name in tables_with_class_id:
        op.execute(text(f"""
            DO $$
            DECLARE
                fk_name TEXT;
            BEGIN
                SELECT tc.constraint_name INTO fk_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.table_name = '{table_name}'
                AND tc.constraint_type = 'FOREIGN KEY'
                AND kcu.column_name = '{column_name}'
                AND tc.table_schema = 'public'
                LIMIT 1;
                
                IF fk_name IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I', '{table_name}', fk_name);
                END IF;
            END $$;
        """))
    
    # Reverter colunas filhas
    for table_name, column_name in reversed(tables_with_class_id):
        result = connection.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = '{table_name}' 
                AND column_name = '{column_name}'
            );
        """))
        
        if result.scalar():
            op.execute(text(f"""
                ALTER TABLE {table_name} 
                ALTER COLUMN {column_name} TYPE VARCHAR USING {column_name}::VARCHAR;
            """))
    
    # Reverter class.id
    op.execute(text("""
        ALTER TABLE class 
        ALTER COLUMN id TYPE VARCHAR USING id::VARCHAR;
    """))
    
    # Recriar FKs
    for table_name, column_name in tables_with_class_id:
        result = connection.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = '{table_name}' 
                AND column_name = '{column_name}'
            );
        """))
        
        if result.scalar():
            op.execute(text(f"""
                ALTER TABLE {table_name}
                ADD CONSTRAINT fk_{table_name}_{column_name}
                FOREIGN KEY ({column_name}) REFERENCES class(id);
            """))
