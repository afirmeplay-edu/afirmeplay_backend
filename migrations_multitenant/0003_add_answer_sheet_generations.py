"""
Migration 0003: Tabela answer_sheet_generations em cada schema city_xxx

Histórico de gerações de ZIP por gabarito (escopos distintos não se sobrescrevem na listagem).

Idempotente: CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS.
"""

import os
import sys
import logging
from datetime import datetime
from typing import List

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

log_filename = f'migration_0003_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

possible_env_paths = [
    'app/.env',
    '../app/.env',
    os.path.join(os.path.dirname(__file__), '..', 'app', '.env'),
]
for env_path in possible_env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info('Arquivo .env carregado: %s', env_path)
        break

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    logger.error('DATABASE_URL não encontrado!')
    sys.exit(1)


def _ddl_for_schema(schema: str) -> List[str]:
    """Uma instrução por execute (psycopg2)."""
    return [
        f'''
CREATE TABLE IF NOT EXISTS "{schema}".answer_sheet_generations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gabarito_id VARCHAR NOT NULL REFERENCES "{schema}".answer_sheet_gabaritos(id) ON DELETE CASCADE,
    job_id VARCHAR(36) NOT NULL,
    scope_type VARCHAR(50),
    scope_snapshot JSONB,
    minio_url VARCHAR(500),
    minio_object_name VARCHAR(500),
    minio_bucket VARCHAR(100),
    zip_generated_at TIMESTAMP,
    total_classes INTEGER,
    total_students INTEGER,
    status VARCHAR(30) NOT NULL DEFAULT 'completed',
    created_by VARCHAR REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''',
        (
            'COMMENT ON TABLE "{schema}".answer_sheet_generations IS '
            "'Histórico de gerações de ZIP por gabarito (escopos distintos)'"
        ).format(schema=schema),
        f'''CREATE INDEX IF NOT EXISTS idx_as_gen_gabarito ON "{schema}".answer_sheet_generations(gabarito_id)''',
        f'''CREATE INDEX IF NOT EXISTS idx_as_gen_job ON "{schema}".answer_sheet_generations(job_id)''',
    ]


def get_city_schemas(cursor) -> List[str]:
    cursor.execute(
        """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name LIKE 'city_%'
        ORDER BY schema_name
        """
    )
    return [row[0] for row in cursor.fetchall()]


def run_migration(dry_run: bool = False):
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    try:
        schemas = get_city_schemas(cursor)
        logger.info('Schemas city_xxx encontrados: %s', len(schemas))
        cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        for schema in schemas:
            if dry_run:
                logger.info('[DRY RUN] Aplicaria DDL em %s', schema)
                continue
            try:
                for stmt in _ddl_for_schema(schema):
                    cursor.execute(stmt)
                logger.info('OK: %s.answer_sheet_generations', schema)
            except Exception as e:
                logger.error('Falha em %s: %s', schema, e, exc_info=True)
                raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    run_migration(dry_run=dry)
