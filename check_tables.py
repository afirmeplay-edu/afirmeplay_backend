#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar se todas as tabelas necessarias existem
"""
import os
import sys

def check_tables():
    """Verifica se todas as tabelas necessarias existem"""
    try:
        import psycopg2
        
        # Configuracao do banco
        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/innovaplay')
        
        # Extrair parametros da URL
        if DATABASE_URL.startswith('postgresql://'):
            url_parts = DATABASE_URL.replace('postgresql://', '').split('@')
            if len(url_parts) == 2:
                auth, host_db = url_parts
                user_pass = auth.split(':')
                host_port_db = host_db.split('/')
                
                if len(user_pass) == 2 and len(host_port_db) == 2:
                    user, password = user_pass
                    host_port, database = host_port_db
                    host, port = host_port.split(':') if ':' in host_port else (host_port, '5432')
                    
                    # Conectar ao banco
                    conn = psycopg2.connect(
                        host=host,
                        port=port,
                        database=database,
                        user=user,
                        password=password
                    )
                    
                    cursor = conn.cursor()
                    
                    # Lista de tabelas necessarias
                    required_tables = [
                        'test',
                        'student', 
                        'test_sessions',
                        'evaluation_results'
                    ]
                    
                    print("Verificando tabelas necessarias...")
                    
                    for table in required_tables:
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_schema = 'public' 
                                AND table_name = %s
                            );
                        """, (table,))
                        
                        exists = cursor.fetchone()[0]
                        status = "EXISTE" if exists else "NAO EXISTE"
                        print(f"  {table}: {status}")
                    
                    cursor.close()
                    conn.close()
                    
                else:
                    print("Erro: Formato de URL invalido")
                    sys.exit(1)
            else:
                print("Erro: Formato de URL invalido")
                sys.exit(1)
        else:
            print("Erro: URL deve comecar com postgresql://")
            sys.exit(1)
            
    except ImportError:
        print("Erro: psycopg2 nao instalado. Execute: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("=== Verificacao de Tabelas ===")
    check_tables()
    print("=== Fim da Verificacao ===") 