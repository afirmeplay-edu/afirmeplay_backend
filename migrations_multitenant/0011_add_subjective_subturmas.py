"""
Migration 0011: coluna subturmas em subjective_tests.

Ids de subturma ADAP no escopo da prova subjetiva.
Idempotente: ADD COLUMN IF NOT EXISTS em todo schema city_* que já tem a tabela.
"""

import os
import sys
import logging
from datetime import datetime
from typing import List

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

log_filename = f'migration_0011_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

possible_env_paths = [
    "app/.env",
    "../app/.env",
    os.path.join(os.path.dirname(__file__), "..", "app", ".env"),
]
for env_path in possible_env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info("Arquivo .env carregado: %s", env_path)
        break

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL não encontrado!")
    sys.exit(1)


def _safe_schema(schema: str) -> str:
    if not schema.replace("_", "").isalnum() or not schema.startswith("city_"):
        raise ValueError(f"Schema inválido: {schema}")
    return schema


def run_migration(dry_run: bool = False):
    conn = psycopg2.connect(DATABASE_URL.strip())
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT table_schema
            FROM information_schema.tables
            WHERE table_name = 'subjective_tests'
              AND table_schema LIKE 'city_%'
            ORDER BY table_schema
            """
        )
        schemas: List[str] = [row[0] for row in cursor.fetchall()]
        logger.info("Schemas com subjective_tests: %s", len(schemas))
        errors = 0
        for schema in schemas:
            try:
                schema = _safe_schema(schema)
                statements = [
                    f'ALTER TABLE "{schema}".subjective_tests ADD COLUMN IF NOT EXISTS subturmas JSON',
                    (
                        f'COMMENT ON COLUMN "{schema}".subjective_tests.subturmas IS '
                        "'Ids de subturma ADAP no escopo da prova. A turma regular continua em classes.'"
                    ),
                ]
                for stmt in statements:
                    logger.info("[%s] %s", schema, stmt.split("\n")[0][:90])
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
    run_migration(dry_run="--dry-run" in sys.argv)
