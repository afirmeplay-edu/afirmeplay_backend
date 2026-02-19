"""
Migration 0002: Consolidar todas as questões em public.question

Este script atualiza a arquitetura de questões para usar apenas public.question:
- Adiciona scope_type 'PRIVATE' ao enum (além de GLOBAL e CITY)
- Adiciona campo owner_user_id para questões privadas
- Migra dados de city_xxx.question para public.question (se houver)
- Remove tabela city_xxx.question de todos os schemas

Scopes finais:
- GLOBAL: Questões do Admin (compartilhadas com todos)
- CITY: Questões do Tecadm (compartilhadas no município)
- PRIVATE: Questões de Professor/Coordenador/Diretor (privadas do usuário)

⚠️ IMPORTANTE:
- Script é IDEMPOTENTE (pode rodar múltiplas vezes)
- Migra dados antes de dropar tabelas
- NÃO perde dados de questões existentes
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Configurar logging com UTF-8 para Windows
log_filename = f'migration_0002_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configurar stdout para UTF-8 no Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Carregar variáveis de ambiente
possible_env_paths = [
    'app/.env',
    '../app/.env',
    os.path.join(os.path.dirname(__file__), '..', 'app', '.env')
]

for env_path in possible_env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f"Arquivo .env carregado: {env_path}")
        break

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    logger.error("DATABASE_URL não encontrado!")
    sys.exit(1)


class QuestionConsolidationMigration:
    """Consolidação de questões em public.question"""
    
    def __init__(self, database_url: str, dry_run: bool = False):
        self.database_url = database_url
        self.dry_run = dry_run
        self.conn = None
        self.cursor = None
        
    def __enter__(self):
        """Context manager - conectar ao banco"""
        self.conn = psycopg2.connect(self.database_url)
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        self.cursor = self.conn.cursor()
        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}Conectado ao banco de dados")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager - fechar conexão"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Conexão fechada")
        
    def execute(self, sql: str, params=None, description: str = ""):
        """Executa SQL com logging e dry-run"""
        if self.dry_run:
            logger.info(f"[DRY RUN] {description}")
            logger.debug(f"[DRY RUN SQL] {sql}")
            return None
        
        try:
            if description:
                logger.info(description)
            self.cursor.execute(sql, params)
            return self.cursor
        except Exception as e:
            logger.error(f"Erro ao executar: {description}")
            logger.error(f"SQL: {sql}")
            logger.error(f"Erro: {e}")
            raise
    
    def get_city_schemas(self) -> List[str]:
        """Buscar todos os schemas city_xxx"""
        self.cursor.execute("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name LIKE 'city_%'
            ORDER BY schema_name
        """)
        schemas = [row[0] for row in self.cursor.fetchall()]
        logger.info(f"Encontrados {len(schemas)} schemas city_xxx")
        return schemas
    
    def add_private_scope_to_enum(self):
        """1. Adicionar 'PRIVATE' ao enum question_scope_type"""
        logger.info("=" * 80)
        logger.info("ETAPA 1: Adicionando scope PRIVATE ao enum")
        logger.info("=" * 80)
        
        # Verificar se PRIVATE já existe
        check_sql = """
        SELECT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumlabel = 'PRIVATE' 
            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'question_scope_type')
        );
        """
        self.cursor.execute(check_sql)
        exists = self.cursor.fetchone()[0]
        
        if exists:
            logger.info("  [OK] Enum já possui valor 'PRIVATE'")
            return
        
        # Adicionar PRIVATE ao enum
        enum_sql = """
        ALTER TYPE question_scope_type ADD VALUE IF NOT EXISTS 'PRIVATE';
        """
        self.execute(enum_sql, description="  => Adicionando 'PRIVATE' ao enum question_scope_type")
        logger.info("  [OK] Scope 'PRIVATE' adicionado ao enum\n")
    
    def add_owner_user_id_column(self):
        """2. Adicionar campo owner_user_id em public.question"""
        logger.info("=" * 80)
        logger.info("ETAPA 2: Adicionando campo owner_user_id")
        logger.info("=" * 80)
        
        column_sql = """
        ALTER TABLE public.question 
        ADD COLUMN IF NOT EXISTS owner_user_id VARCHAR REFERENCES public.users(id);
        """
        self.execute(
            column_sql,
            description="  => Adicionando coluna owner_user_id em public.question"
        )
        
        # Comentário na coluna
        comment_sql = """
        COMMENT ON COLUMN public.question.owner_user_id IS 
        'ID do usuário dono da questão (para questões PRIVATE)';
        """
        self.execute(comment_sql)
        
        # Criar índice
        index_sql = """
        CREATE INDEX IF NOT EXISTS idx_question_owner_user ON public.question(owner_user_id);
        """
        self.execute(index_sql, description="  => Criando índice em owner_user_id")
        
        logger.info("  [OK] Campo owner_user_id adicionado\n")
    
    def migrate_city_questions_to_public(self, schema: str):
        """3. Migrar questões de city_xxx.question para public.question"""
        logger.info(f"  Verificando questões em {schema}.question...")
        
        # Verificar se a tabela existe
        check_table_sql = f"""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = '{schema}' 
            AND table_name = 'question'
        );
        """
        self.cursor.execute(check_table_sql)
        table_exists = self.cursor.fetchone()[0]
        
        if not table_exists:
            logger.info(f"    [OK] Tabela {schema}.question não existe (nada para migrar)")
            return 0
        
        # Contar questões na tabela city
        count_sql = f"SELECT COUNT(*) FROM {schema}.question;"
        self.cursor.execute(count_sql)
        count = self.cursor.fetchone()[0]
        
        if count == 0:
            logger.info(f"    [OK] Tabela {schema}.question está vazia (nada para migrar)")
            return 0
        
        logger.info(f"    [!] Encontradas {count} questões em {schema}.question para migrar")
        
        if self.dry_run:
            logger.info(f"    [DRY RUN] Migraria {count} questões para public.question")
            return count
        
        # Migrar questões para public.question com scope PRIVATE
        migrate_sql = f"""
        INSERT INTO public.question (
            id, number, text, formatted_text, secondstatement, images,
            subject_id, title, description, command, subtitle, alternatives,
            skill, grade_level, education_stage_id, difficulty_level,
            correct_answer, formatted_solution, question_type, value,
            topics, version, created_by, created_at, updated_at, last_modified_by,
            scope_type, owner_user_id
        )
        SELECT 
            id, number, text, formatted_text, secondstatement, images,
            subject_id, title, description, command, subtitle, alternatives,
            skill, grade_level, education_stage_id, difficulty_level,
            correct_answer, formatted_solution, question_type, value,
            topics, version, created_by, created_at, updated_at, last_modified_by,
            'PRIVATE'::question_scope_type, created_by  -- scope=PRIVATE, owner=creator
        FROM {schema}.question
        ON CONFLICT (id) DO UPDATE SET
            scope_type = 'PRIVATE',
            owner_user_id = EXCLUDED.created_by;
        """
        
        try:
            self.execute(
                migrate_sql,
                description=f"    => Migrando {count} questões para public.question"
            )
            logger.info(f"    [OK] {count} questões migradas com sucesso")
            return count
        except Exception as e:
            logger.error(f"    [ERRO] Falha ao migrar questões: {e}")
            raise
    
    def drop_city_question_table(self, schema: str):
        """4. Dropar tabela city_xxx.question"""
        # Verificar se a tabela existe
        check_table_sql = f"""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = '{schema}' 
            AND table_name = 'question'
        );
        """
        self.cursor.execute(check_table_sql)
        table_exists = self.cursor.fetchone()[0]
        
        if not table_exists:
            logger.info(f"    [OK] Tabela {schema}.question não existe (nada para dropar)")
            return
        
        drop_sql = f"DROP TABLE IF EXISTS {schema}.question CASCADE;"
        self.execute(
            drop_sql,
            description=f"    => Removendo tabela {schema}.question"
        )
        logger.info(f"    [OK] Tabela {schema}.question removida")
    
    def run(self):
        """Executar migration completa"""
        logger.info("\n" + "=" * 80)
        logger.info("INICIANDO MIGRATION 0002: Consolidação de Questões")
        logger.info("=" * 80 + "\n")
        
        try:
            # Etapa 1: Adicionar PRIVATE ao enum
            self.add_private_scope_to_enum()
            
            # Etapa 2: Adicionar owner_user_id
            self.add_owner_user_id_column()
            
            # Etapa 3 e 4: Processar cada schema city
            schemas = self.get_city_schemas()
            total_migrated = 0
            
            if schemas:
                logger.info("=" * 80)
                logger.info(f"ETAPA 3 e 4: Migrar e remover tabelas question de {len(schemas)} schemas")
                logger.info("=" * 80)
                
                for schema in schemas:
                    logger.info(f"\nProcessando {schema}:")
                    
                    # Migrar dados
                    migrated = self.migrate_city_questions_to_public(schema)
                    total_migrated += migrated
                    
                    # Dropar tabela
                    self.drop_city_question_table(schema)
            
            # Resumo final
            logger.info("\n" + "=" * 80)
            logger.info("RESUMO DA MIGRATION")
            logger.info("=" * 80)
            logger.info(f"✅ Enum atualizado com scope 'PRIVATE'")
            logger.info(f"✅ Campo owner_user_id adicionado em public.question")
            logger.info(f"✅ {total_migrated} questões migradas de city_xxx.question → public.question")
            logger.info(f"✅ Tabelas city_xxx.question removidas de {len(schemas)} schemas")
            logger.info("=" * 80)
            logger.info("MIGRATION 0002 CONCLUÍDA COM SUCESSO!")
            logger.info("=" * 80 + "\n")
            
        except Exception as e:
            logger.error(f"\n❌ ERRO NA MIGRATION: {e}")
            raise


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migration 0002: Consolidar questões em public')
    parser.add_argument('--dry-run', action='store_true', help='Executar em modo dry-run (não faz alterações)')
    args = parser.parse_args()
    
    if not DATABASE_URL:
        logger.error("❌ DATABASE_URL não configurado!")
        sys.exit(1)
    
    logger.info(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'local'}")
    
    if args.dry_run:
        logger.info("⚠️  MODO DRY-RUN ATIVADO - Nenhuma alteração será feita\n")
    
    try:
        with QuestionConsolidationMigration(DATABASE_URL, dry_run=args.dry_run) as migration:
            migration.run()
    except Exception as e:
        logger.error(f"❌ Migration falhou: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
