#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script simples para criar a tabela evaluation_results
"""
import os
import sys

def create_table_simple():
    """Cria a tabela usando psycopg2"""
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
                    
                    # Verificar se a tabela existe
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'evaluation_results'
                        );
                    """)
                    
                    table_exists = cursor.fetchone()[0]
                    
                    if table_exists:
                        print("Tabela evaluation_results ja existe!")
                        return
                    
                    # Criar a tabela
                    cursor.execute("""
                        CREATE TABLE evaluation_results (
                            id VARCHAR PRIMARY KEY,
                            test_id VARCHAR NOT NULL REFERENCES test(id),
                            student_id VARCHAR NOT NULL REFERENCES student(id),
                            session_id VARCHAR NOT NULL REFERENCES test_sessions(id),
                            correct_answers INTEGER NOT NULL,
                            total_questions INTEGER NOT NULL,
                            score_percentage FLOAT NOT NULL,
                            grade FLOAT NOT NULL,
                            proficiency FLOAT NOT NULL,
                            classification VARCHAR(50) NOT NULL,
                            calculated_at TIMESTAMP,
                            UNIQUE(test_id, student_id)
                        );
                    """)
                    
                    # Criar indices
                    cursor.execute("CREATE INDEX idx_evaluation_results_test_id ON evaluation_results(test_id);")
                    cursor.execute("CREATE INDEX idx_evaluation_results_student_id ON evaluation_results(student_id);")
                    cursor.execute("CREATE INDEX idx_evaluation_results_session_id ON evaluation_results(session_id);")
                    cursor.execute("CREATE INDEX idx_evaluation_results_calculated_at ON evaluation_results(calculated_at);")
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    print("Tabela evaluation_results criada com sucesso!")
                    print("Indices criados com sucesso!")
                    
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
    print("Iniciando migracao simples...")
    create_table_simple()
    print("Migracao concluida!") 