#!/usr/bin/env python3
"""
Script para verificar se há migrações pendentes usando Alembic.
"""

import os
import sys
from flask import Flask
from flask_migrate import Migrate
from dotenv import load_dotenv

# Adicionar o diretório do app ao path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Carregar variáveis de ambiente
load_dotenv('app/.env')

def create_app():
    """Cria uma instância da aplicação Flask para verificação"""
    app = Flask(__name__)
    
    # Configuração do banco
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Importar e configurar extensões
    from app import db
    db.init_app(app)
    
    # Configurar migrações
    migrate = Migrate(app, db)
    
    return app

def check_migrations():
    """Verifica se há migrações pendentes"""
    try:
        app = create_app()
        
        with app.app_context():
            from flask_migrate import current, heads, show
            
            print("=" * 60)
            print("VERIFICAÇÃO DE MIGRAÇÕES")
            print("=" * 60)
            
            # Verificar versão atual
            try:
                current_revision = current()
                print(f"Revisão atual: {current_revision}")
            except Exception as e:
                print(f"Erro ao obter revisão atual: {e}")
                return
            
            # Verificar última migração
            try:
                head_revision = heads()
                print(f"Última migração: {head_revision}")
            except Exception as e:
                print(f"Erro ao obter última migração: {e}")
                return
            
            # Verificar se há migrações pendentes
            if current_revision != head_revision:
                print("⚠️  HÁ MIGRAÇÕES PENDENTES!")
                print("Execute: flask db upgrade")
            else:
                print("✅ Banco de dados está atualizado!")
            
            print("\n" + "=" * 60)
            print("HISTÓRICO DE MIGRAÇÕES:")
            print("=" * 60)
            
            # Mostrar histórico
            try:
                show()
            except Exception as e:
                print(f"Erro ao mostrar histórico: {e}")
                
    except Exception as e:
        print(f"Erro durante verificação: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_migrations()
