"""
Migration 0007: tabela cover_templates em cada schema city_xxx.

Capa de prova física associada à avaliação (tenant.test), não ao município.
Isolamento pelo schema tenant; unique parcial garante um template active por test_id.

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

log_filename = f'migration_0007_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
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
    """DDL inline (não importa Flask/app — este script roda fora do PYTHONPATH)."""
    return [
        f'''
CREATE TABLE IF NOT EXISTS "{schema}".cover_templates (
    id VARCHAR PRIMARY KEY,
    test_id VARCHAR NOT NULL REFERENCES "{schema}".test(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    original_filename VARCHAR(255),
    mime_type VARCHAR(100) NOT NULL,
    source_kind VARCHAR(20) NOT NULL,
    minio_bucket VARCHAR(100) NOT NULL,
    minio_object_name VARCHAR(500) NOT NULL,
    normalized_object_name VARCHAR(500),
    page_count INTEGER NOT NULL DEFAULT 1,
    page_width_pt FLOAT NOT NULL,
    page_height_pt FLOAT NOT NULL,
    rotation INTEGER NOT NULL DEFAULT 0,
    fields JSON NOT NULL DEFAULT '{{"fields": []}}'::json,
    version INTEGER NOT NULL DEFAULT 1,
    created_by VARCHAR REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_cover_templates_status CHECK (status IN ('draft', 'active', 'inactive')),
    CONSTRAINT ck_cover_templates_source_kind CHECK (source_kind IN ('pdf', 'jpeg', 'png'))
)
''',
        f'''COMMENT ON TABLE "{schema}".cover_templates IS 'Templates de capa de prova física por avaliação (tenant.test)' ''',
        f'CREATE INDEX IF NOT EXISTS ix_cover_templates_test_id ON "{schema}".cover_templates(test_id)',
        f'''
CREATE UNIQUE INDEX IF NOT EXISTS uq_cover_templates_one_active_per_test
    ON "{schema}".cover_templates(test_id) WHERE status = 'active'
''',
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
        logger.info("Schemas city_*: %s", len(schemas))
        errors = 0
        for schema in schemas:
            try:
                for stmt in _ddl_for_schema(schema):
                    logger.info("[%s] %s", schema, stmt.split("\n")[0][:100])
                    if not dry_run:
                        cursor.execute(stmt)
            except Exception as exc:
                errors += 1
                logger.error("[%s] falha (continua nos demais): %s", schema, exc, exc_info=True)
        logger.info("Concluído. erros: %s", errors)
        if errors:
            sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run_migration(dry_run=dry)
