#!/usr/bin/env python3
"""
Script para aplicar a migração da tabela games
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def get_database_url():
    """Obtém a URL do banco de dados das variáveis de ambiente"""
    return os.getenv('DATABASE_URL', 'postgresql://localhost/innovaplay')

def apply_migration():
    """Aplica a migração da tabela games"""
    try:
        # Conectar ao banco de dados
        conn = psycopg2.connect(get_database_url())
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("Conectado ao banco de dados...")
        
        # Ler o arquivo de migração
        with open('migration_create_games_table.sql', 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print("Aplicando migração da tabela games...")
        
        # Executar a migração
        cursor.execute(migration_sql)
        
        print("Migração aplicada com sucesso!")
        
        # Verificar se a tabela foi criada
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'games'
        """)
        
        if cursor.fetchone():
            print("✓ Tabela 'games' criada com sucesso!")
        else:
            print("✗ Erro: Tabela 'games' não foi criada!")
            return False
        
        # Verificar as colunas da tabela
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'games'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        print("\nColunas da tabela 'games':")
        for column in columns:
            nullable = "NULL" if column[2] == "YES" else "NOT NULL"
            print(f"  - {column[0]}: {column[1]} {nullable}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Erro ao aplicar migração: {e}")
        return False

if __name__ == "__main__":
    print("=== Migração da Tabela Games ===")
    success = apply_migration()
    
    if success:
        print("\n✅ Migração concluída com sucesso!")
        sys.exit(0)
    else:
        print("\n❌ Falha na migração!")
        sys.exit(1) 