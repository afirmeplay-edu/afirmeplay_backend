"""
Migração para atualizar os campos application e expiration da tabela class_test
para incluir timezone (timezone=True)
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

def update_class_test_timezone():
    """Atualiza os campos application e expiration para incluir timezone"""
    
    app = create_app()
    
    with app.app_context():
        try:
            print("🔄 Iniciando migração para adicionar timezone aos campos application e expiration...")
            
            # Verificar se os campos já têm timezone
            check_sql = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'class_test' 
            AND column_name IN ('application', 'expiration')
            ORDER BY column_name;
            """
            
            result = db.session.execute(text(check_sql))
            columns_info = result.fetchall()
            
            print("📋 Informações atuais dos campos:")
            for col in columns_info:
                print(f"  - {col.column_name}: {col.data_type} (nullable: {col.is_nullable})")
            
            # Verificar se precisa de migração
            needs_migration = False
            for col in columns_info:
                if col.column_name in ['application', 'expiration'] and 'timezone' not in col.data_type:
                    needs_migration = True
                    break
            
            if not needs_migration:
                print("✅ Campos já possuem timezone. Nenhuma migração necessária.")
                return
            
            print("🔧 Executando migração...")
            
            # SQL para alterar os campos para incluir timezone
            # Nota: PostgreSQL requer recriar a tabela para alterar timezone
            # Vamos usar uma abordagem mais segura
            
            # 1. Criar colunas temporárias com timezone
            print("   📝 Criando colunas temporárias...")
            db.session.execute(text("""
                ALTER TABLE class_test 
                ADD COLUMN application_tz TIMESTAMP WITH TIME ZONE,
                ADD COLUMN expiration_tz TIMESTAMP WITH TIME ZONE;
            """))
            
            # 2. Copiar dados existentes convertendo para timezone
            print("   📋 Copiando dados existentes...")
            db.session.execute(text("""
                UPDATE class_test 
                SET 
                    application_tz = application AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo',
                    expiration_tz = expiration AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo'
                WHERE application IS NOT NULL OR expiration IS NOT NULL;
            """))
            
            # 3. Remover colunas antigas
            print("   🗑️ Removendo colunas antigas...")
            db.session.execute(text("""
                ALTER TABLE class_test 
                DROP COLUMN application,
                DROP COLUMN expiration;
            """))
            
            # 4. Renomear colunas temporárias
            print("   🔄 Renomeando colunas...")
            db.session.execute(text("""
                ALTER TABLE class_test 
                RENAME COLUMN application_tz TO application;
            """))
            
            db.session.execute(text("""
                ALTER TABLE class_test 
                RENAME COLUMN expiration_tz TO expiration;
            """))
            
            # 5. Adicionar constraints se necessário
            print("   ✅ Adicionando constraints...")
            db.session.execute(text("""
                ALTER TABLE class_test 
                ALTER COLUMN application SET NOT NULL,
                ALTER COLUMN expiration SET NOT NULL;
            """))
            
            db.session.commit()
            
            print("✅ Migração concluída com sucesso!")
            
            # Verificar resultado
            result = db.session.execute(text(check_sql))
            columns_info = result.fetchall()
            
            print("📋 Informações finais dos campos:")
            for col in columns_info:
                print(f"  - {col.column_name}: {col.data_type} (nullable: {col.is_nullable})")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro durante a migração: {str(e)}")
            raise
        finally:
            db.session.close()

if __name__ == "__main__":
    update_class_test_timezone()
