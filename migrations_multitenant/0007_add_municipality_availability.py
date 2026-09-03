"""
Migration 0007: available_to_municipality + available_from em test e gabaritos.

Idempotente: ADD COLUMN IF NOT EXISTS em todos os schemas city_*.
Default true preserva visibilidade das provas/cartões já existentes.
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
    return [
        f'''ALTER TABLE "{schema}".test
            ADD COLUMN IF NOT EXISTS available_to_municipality BOOLEAN NOT NULL DEFAULT true''',
        f'''ALTER TABLE "{schema}".test
            ADD COLUMN IF NOT EXISTS available_from TIMESTAMPTZ''',
        f'''ALTER TABLE "{schema}".answer_sheet_gabaritos
            ADD COLUMN IF NOT EXISTS available_to_municipality BOOLEAN NOT NULL DEFAULT true''',
        f'''ALTER TABLE "{schema}".answer_sheet_gabaritos
            ADD COLUMN IF NOT EXISTS available_from TIMESTAMPTZ''',
        (
            f'COMMENT ON COLUMN "{schema}".test.available_to_municipality IS '
            "'Se false, a avaliação não aparece nem pode ser aplicada pelo município (exceto admin/tecadm)'"
        ),
        (
            f'COMMENT ON COLUMN "{schema}".test.available_from IS '
            "'Se preenchido, o município só vê/aplica a partir desta data/hora'"
        ),
        (
            f'COMMENT ON COLUMN "{schema}".answer_sheet_gabaritos.available_to_municipality IS '
            "'Se false, o cartão não aparece nem pode ser gerado/baixado pelo município (exceto admin/tecadm)'"
        ),
        (
            f'COMMENT ON COLUMN "{schema}".answer_sheet_gabaritos.available_from IS '
            "'Se preenchido, o município só vê/gera a partir desta data/hora'"
        ),
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


def _table_exists(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_name = %s
        LIMIT 1
        """,
        (schema, table),
    )
    return cursor.fetchone() is not None


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
                if not _table_exists(cursor, schema, "test") and not _table_exists(
                    cursor, schema, "answer_sheet_gabaritos"
                ):
                    logger.warning("[%s] tabelas ausentes — pulando", schema)
                    continue
                for stmt in _ddl_for_schema(schema):
                    logger.info("[%s] %s", schema, stmt.strip().split("\n")[0][:90])
                    if not dry_run:
                        try:
                            cursor.execute(stmt)
                        except Exception as col_exc:
                            logger.warning("[%s] stmt ignorado: %s", schema, col_exc)
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
