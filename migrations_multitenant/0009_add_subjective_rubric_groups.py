"""
Migration 0009: grupos de critérios da rubrica subjetiva.

Cria subjective_rubric_groups, adiciona rubric_group_id em marks/questions,
migra avaliações existentes para um grupo padrão e troca o unique de code
para (grupo, code).

Idempotente.
"""

import os
import sys
import logging
from datetime import datetime

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

log_filename = f"migration_0009_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.city_schema_service import get_subjective_rubric_groups_upgrade_ddl  # noqa: E402


def _split_ddl(ddl: str):
    parts = []
    buffer = []
    in_do = False
    for line in ddl.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DO $$"):
            in_do = True
        buffer.append(line)
        if in_do:
            if stripped.upper().startswith("END $$"):
                in_do = False
                parts.append("\n".join(buffer).strip())
                buffer = []
        elif stripped.endswith(";"):
            parts.append("\n".join(buffer).strip().rstrip(";"))
            buffer = []
    if buffer:
        leftover = "\n".join(buffer).strip().rstrip(";")
        if leftover:
            parts.append(leftover)
    return [p for p in parts if p]


def get_city_schemas(cursor):
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
                for stmt in _split_ddl(get_subjective_rubric_groups_upgrade_ddl(schema)):
                    logger.info("[%s] %s", schema, stmt.split("\n")[0][:120])
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
