#!/usr/bin/env python3
"""
Script para aplicar a migração do sistema de cronômetro
Remove o campo actual_start_time da tabela test_sessions
"""

import sys
import os
from datetime import datetime

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from sqlalchemy import text

def apply_timer_migration():
    """
    Aplica a migração para remover o campo actual_start_time
    """
    
    app = create_app()
    
    with app.app_context():
        print("🔄 Iniciando migração do sistema de cronômetro...")
        
        try:
            # 1. Verificar se a coluna actual_start_time existe
            print("🔍 Verificando se a coluna actual_start_time existe...")
            
            check_column_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'test_sessions' 
                AND column_name = 'actual_start_time'
            """)
            
            result = db.session.execute(check_column_query)
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("✅ Coluna actual_start_time não existe, nada a fazer")
                return
            
            print("📋 Coluna actual_start_time encontrada, iniciando migração...")
            
            # 2. Migrar dados se necessário (copiar actual_start_time para started_at se started_at for NULL)
            print("📊 Migrando dados...")
            
            migrate_data_query = text("""
                UPDATE test_sessions 
                SET started_at = actual_start_time 
                WHERE started_at IS NULL 
                AND actual_start_time IS NOT NULL
            """)
            
            result = db.session.execute(migrate_data_query)
            migrated_rows = result.rowcount
            
            print(f"✅ {migrated_rows} registros migrados")
            
            # 3. Remover a coluna actual_start_time
            print("🗑️ Removendo coluna actual_start_time...")
            
            drop_column_query = text("ALTER TABLE test_sessions DROP COLUMN actual_start_time")
            db.session.execute(drop_column_query)
            
            # 4. Adicionar comentário na tabela
            print("📝 Adicionando comentário na tabela...")
            
            comment_query = text("""
                COMMENT ON TABLE test_sessions IS 'Tabela de sessões de teste - Frontend responsável pelo cronômetro'
            """)
            db.session.execute(comment_query)
            
            # 5. Commit das mudanças
            db.session.commit()
            
            print("🎉 Migração concluída com sucesso!")
            print("📋 Resumo:")
            print(f"   - {migrated_rows} registros migrados")
            print("   - Coluna actual_start_time removida")
            print("   - Comentário adicionado na tabela")
            print("\n💡 O sistema agora usa a nova abordagem de cronômetro no frontend")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro durante a migração: {str(e)}")
            print("🔄 Rollback realizado")
            return
        
        # 6. Verificar resultado
        print("\n🔍 Verificando resultado da migração...")
        
        try:
            # Tentar acessar a coluna removida (deve falhar)
            test_query = text("SELECT actual_start_time FROM test_sessions LIMIT 1")
            db.session.execute(test_query)
            print("⚠️  AVISO: Coluna actual_start_time ainda existe!")
        except Exception as e:
            if "actual_start_time" in str(e):
                print("✅ Confirmação: Coluna actual_start_time foi removida com sucesso")
            else:
                print(f"⚠️  Erro inesperado: {str(e)}")
        
        # 7. Mostrar estatísticas finais
        print("\n📊 Estatísticas finais:")
        
        try:
            count_query = text("SELECT COUNT(*) as total FROM test_sessions")
            result = db.session.execute(count_query)
            total_sessions = result.fetchone()[0]
            
            active_query = text("SELECT COUNT(*) as active FROM test_sessions WHERE status = 'em_andamento'")
            result = db.session.execute(active_query)
            active_sessions = result.fetchone()[0]
            
            print(f"   📈 Total de sessões: {total_sessions}")
            print(f"   🟢 Sessões ativas: {active_sessions}")
            
        except Exception as e:
            print(f"⚠️  Erro ao obter estatísticas: {str(e)}")

if __name__ == "__main__":
    print("🚀 Script de migração do sistema de cronômetro")
    print("=" * 50)
    apply_timer_migration()
    print("=" * 50)
    print("✅ Script finalizado") 