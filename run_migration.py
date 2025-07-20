#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para executar a migracao da tabela evaluation_results
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

def run_migration():
    """Executa a migracao da tabela evaluation_results"""
    
    # Configuracao do banco de dados
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/innovaplay')
    
    try:
        # Criar conexao com o banco
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Verificar se a tabela ja existe
            check_table = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'evaluation_results'
                );
            """)
            
            result = conn.execute(check_table)
            table_exists = result.scalar()
            
            if table_exists:
                print("Tabela evaluation_results ja existe!")
                return
            
            # Criar a tabela
            create_table = text("""
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
            
            conn.execute(create_table)
            conn.commit()
            
            print("Tabela evaluation_results criada com sucesso!")
            
            # Criar indices para melhor performance
            create_indexes = text("""
                CREATE INDEX idx_evaluation_results_test_id ON evaluation_results(test_id);
                CREATE INDEX idx_evaluation_results_student_id ON evaluation_results(student_id);
                CREATE INDEX idx_evaluation_results_session_id ON evaluation_results(session_id);
                CREATE INDEX idx_evaluation_results_calculated_at ON evaluation_results(calculated_at);
            """)
            
            conn.execute(create_indexes)
            conn.commit()
            
            print("Indices criados com sucesso!")
            
    except ProgrammingError as e:
        print(f"Erro de programacao: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Iniciando migracao da tabela evaluation_results...")
    run_migration()
    print("Migracao concluida!") 