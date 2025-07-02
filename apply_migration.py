#!/usr/bin/env python3
"""
Script para aplicar migração: adicionar campo end_time à tabela test
"""

from app import create_app, db
from sqlalchemy import text
import sys

def apply_migration():
    """Aplica a migração para adicionar o campo end_time"""
    app = create_app()
    
    with app.app_context():
        try:
            # Verificar se o campo já existe
            result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='test' AND column_name='end_time'"))
            if result.fetchone():
                print("❌ Campo 'end_time' já existe na tabela 'test'")
                return False
            
            print("🔄 Aplicando migração: adicionando campo 'end_time' à tabela 'test'...")
            
            # Adicionar a coluna end_time
            db.session.execute(text("ALTER TABLE test ADD COLUMN end_time TIMESTAMP"))
            
            # Adicionar comentário (opcional - pode falhar em alguns bancos)
            try:
                db.session.execute(text("COMMENT ON COLUMN test.end_time IS 'Data e hora de término da disponibilidade da avaliação'"))
            except Exception as e:
                print(f"⚠️  Aviso: Não foi possível adicionar comentário: {e}")
            
            # Adicionar índice (opcional)
            try:
                db.session.execute(text("CREATE INDEX idx_test_end_time ON test(end_time)"))
            except Exception as e:
                print(f"⚠️  Aviso: Não foi possível criar índice: {e}")
            
            # Commit das mudanças
            db.session.commit()
            print("✅ Migração aplicada com sucesso!")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao aplicar migração: {e}")
            return False

if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1) 