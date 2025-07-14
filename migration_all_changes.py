#!/usr/bin/env python3
"""
Script de migração para aplicar todas as alterações de banco de dados
realizadas durante o desenvolvimento do sistema de avaliações.

Este script deve ser executado em um banco de dados limpo ou para aplicar
as alterações que foram feitas durante nossa conversa.
"""

import psycopg2
import sys
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurações do banco de dados
DB_CONFIG = {
    'host': 'aws-0-us-east-2.pooler.supabase.com',
    'database': 'innovdatabase',
    'user': 'postgres.qtipomtmxkdlhaxltosg',
    'password': 'XbeNANqRMDZxLnUtKwCxErScBU4Ka2su',
    'port': 6543
}

def connect_db():
    """Conecta ao banco de dados"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        return conn
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco: {e}")
        sys.exit(1)

def execute_sql(conn, sql, description):
    """Executa um comando SQL com tratamento de erro"""
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        logger.info(f"✅ {description}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Erro ao executar {description}: {e}")
        return False

def check_column_exists(conn, table_name, column_name):
    """Verifica se uma coluna existe na tabela"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        """, (table_name, column_name))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Erro ao verificar coluna {column_name} em {table_name}: {e}")
        return False

def check_table_exists(conn, table_name):
    """Verifica se uma tabela existe"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = %s
        """, (table_name,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Erro ao verificar tabela {table_name}: {e}")
        return False

def migration_1_remove_actual_start_time(conn):
    """Migração 1: Remove a coluna actual_start_time da tabela test_sessions"""
    logger.info("🔄 Iniciando migração 1: Remover coluna actual_start_time")
    
    if check_column_exists(conn, 'test_sessions', 'actual_start_time'):
        sql = "ALTER TABLE test_sessions DROP COLUMN actual_start_time;"
        return execute_sql(conn, sql, "Coluna actual_start_time removida")
    else:
        logger.info("ℹ️ Coluna actual_start_time não existe, pulando...")
        return True

def migration_2_add_correction_fields(conn):
    """Migração 2: Adiciona campos para correção manual"""
    logger.info("🔄 Iniciando migração 2: Adicionar campos de correção")
    
    # Adicionar campos na tabela student_answers
    fields_to_add = [
        ("student_answers", "is_correct", "BOOLEAN DEFAULT NULL"),
        ("student_answers", "manual_score", "DECIMAL(5,2) DEFAULT NULL"),
        ("student_answers", "feedback", "TEXT"),
        ("student_answers", "corrected_by", "VARCHAR(255)"),
        ("student_answers", "corrected_at", "TIMESTAMP"),
        ("test_sessions", "manual_score", "DECIMAL(5,2) DEFAULT NULL"),
        ("test_sessions", "feedback", "TEXT"),
        ("test_sessions", "corrected_by", "VARCHAR(255)"),
        ("test_sessions", "corrected_at", "TIMESTAMP")
    ]
    
    for table, column, definition in fields_to_add:
        if not check_column_exists(conn, table, column):
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {definition};"
            if not execute_sql(conn, sql, f"Coluna {column} adicionada em {table}"):
                return False
        else:
            logger.info(f"ℹ️ Coluna {column} já existe em {table}, pulando...")
    
    return True

def migration_3_add_foreign_keys(conn):
    """Migração 3: Adiciona foreign keys para campos de correção"""
    logger.info("🔄 Iniciando migração 3: Adicionar foreign keys")
    
    # Verificar se a tabela users existe
    if check_table_exists(conn, 'users'):
        fk_constraints = [
            ("student_answers", "corrected_by", "users", "id"),
            ("test_sessions", "corrected_by", "users", "id")
        ]
        
        for table, column, ref_table, ref_column in fk_constraints:
            if check_column_exists(conn, table, column):
                constraint_name = f"fk_{table}_{column}_{ref_table}"
                sql = f"""
                    ALTER TABLE {table} 
                    ADD CONSTRAINT {constraint_name} 
                    FOREIGN KEY ({column}) REFERENCES {ref_table}({ref_column})
                    ON DELETE SET NULL;
                """
                try:
                    execute_sql(conn, sql, f"Foreign key {constraint_name} adicionada")
                except Exception as e:
                    logger.warning(f"⚠️ Não foi possível adicionar foreign key {constraint_name}: {e}")
    
    return True

def migration_4_create_indexes(conn):
    """Migração 4: Cria índices para melhor performance"""
    logger.info("🔄 Iniciando migração 4: Criar índices")
    
    indexes = [
        ("idx_test_sessions_student_test", "test_sessions", "(student_id, test_id)"),
        ("idx_test_sessions_status", "test_sessions", "(status)"),
        ("idx_student_answers_student_test", "student_answers", "(student_id, test_id)"),
        ("idx_student_answers_question", "student_answers", "(question_id)"),
        ("idx_test_sessions_submitted_at", "test_sessions", "(submitted_at)"),
        ("idx_test_sessions_started_at", "test_sessions", "(started_at)")
    ]
    
    for index_name, table, columns in indexes:
        sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} {columns};"
        execute_sql(conn, sql, f"Índice {index_name} criado")
    
    return True

def migration_5_create_views(conn):
    """Migração 5: Cria views para consultas comuns"""
    logger.info("🔄 Iniciando migração 5: Criar views")
    
    # View para avaliações prontas para correção
    view_sql = """
    CREATE OR REPLACE VIEW evaluations_for_correction AS
    SELECT 
        ts.id as session_id,
        ts.student_id,
        s.name as student_name,
        ts.test_id,
        t.title as test_title,
        ts.submitted_at,
        ts.total_questions,
        ts.correct_answers,
        ts.score,
        ts.status,
        COUNT(sa.id) as total_answers,
        COUNT(CASE WHEN sa.is_correct IS NULL THEN 1 END) as uncorrected_answers
    FROM test_sessions ts
    JOIN student s ON ts.student_id = s.id
    JOIN test t ON ts.test_id = t.id
    LEFT JOIN student_answers sa ON ts.student_id = sa.student_id AND ts.test_id = sa.test_id
    WHERE ts.status = 'finalizada' AND ts.submitted_at IS NOT NULL
    GROUP BY ts.id, ts.student_id, s.name, ts.test_id, t.title, ts.submitted_at, 
             ts.total_questions, ts.correct_answers, ts.score, ts.status
    ORDER BY ts.submitted_at DESC;
    """
    
    execute_sql(conn, view_sql, "View evaluations_for_correction criada")
    
    return True

def migration_6_update_status_values(conn):
    """Migração 6: Atualiza valores de status para consistência"""
    logger.info("🔄 Iniciando migração 6: Atualizar valores de status")
    
    # Atualizar status de avaliações que podem estar inconsistentes
    status_updates = [
        ("UPDATE test SET status = 'agendada' WHERE status IS NULL OR status = '';", "Status vazio para agendada"),
        ("UPDATE test_sessions SET status = 'em_andamento' WHERE status IS NULL OR status = '';", "Status vazio para em_andamento")
    ]
    
    for sql, description in status_updates:
        execute_sql(conn, sql, description)
    
    return True

def main():
    """Função principal que executa todas as migrações"""
    logger.info("🚀 Iniciando processo de migração do banco de dados")
    
    conn = connect_db()
    
    try:
        # Lista de migrações em ordem
        migrations = [
            ("Remover coluna actual_start_time", migration_1_remove_actual_start_time),
            ("Adicionar campos de correção", migration_2_add_correction_fields),
            ("Adicionar foreign keys", migration_3_add_foreign_keys),
            ("Criar índices", migration_4_create_indexes),
            ("Criar views", migration_5_create_views),
            ("Atualizar valores de status", migration_6_update_status_values)
        ]
        
        success_count = 0
        total_migrations = len(migrations)
        
        for name, migration_func in migrations:
            logger.info(f"\n📋 Executando: {name}")
            if migration_func(conn):
                success_count += 1
            else:
                logger.error(f"❌ Falha na migração: {name}")
                break
        
        if success_count == total_migrations:
            logger.info(f"\n🎉 Todas as {total_migrations} migrações foram executadas com sucesso!")
            logger.info("✅ Banco de dados atualizado e pronto para uso")
        else:
            logger.error(f"\n⚠️ {success_count}/{total_migrations} migrações executadas com sucesso")
            logger.error("❌ Algumas migrações falharam")
            
    except Exception as e:
        logger.error(f"❌ Erro durante a migração: {e}")
        conn.rollback()
    finally:
        conn.close()
        logger.info("🔒 Conexão com banco de dados fechada")

if __name__ == "__main__":
    # Instruções de uso
    print("=" * 60)
    print("SCRIPT DE MIGRAÇÃO - INNOVAPLAY BACKEND")
    print("=" * 60)
    print()
    print("⚠️  ATENÇÃO: Antes de executar este script:")
    print("1. Faça backup do seu banco de dados")
    print("2. Atualize as configurações de conexão no script")
    print("3. Teste em um ambiente de desenvolvimento primeiro")
    print()
    print("Configurações atuais do banco:")
    for key, value in DB_CONFIG.items():
        if key == 'password':
            print(f"   {key}: {'*' * len(str(value))}")
        else:
            print(f"   {key}: {value}")
    print()
    
    response = input("Deseja continuar com a migração? (s/N): ")
    if response.lower() in ['s', 'sim', 'y', 'yes']:
        main()
    else:
        print("❌ Migração cancelada pelo usuário")
        sys.exit(0) 