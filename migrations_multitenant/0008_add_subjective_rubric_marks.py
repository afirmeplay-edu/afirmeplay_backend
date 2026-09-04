"""
Migration 0008: marcações configuráveis da rubrica subjetiva.

Cria subjective_rubric_marks, remove o CHECK SIM/PARCIAL/NAO/BRANCO e alarga
subjective_results.value. Faz seed do template padrão nas avaliações existentes.

Idempotente.
"""

import os
import sys
import logging
from datetime import datetime
from typing import List

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

log_filename = f"migration_0008_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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


def _ddl_for_schema(schema: str) -> List[str]:
    return [
        f'''
CREATE TABLE IF NOT EXISTS "{schema}".subjective_rubric_marks (
    id VARCHAR PRIMARY KEY,
    subjective_test_id VARCHAR NOT NULL REFERENCES "{schema}".subjective_tests(id) ON DELETE CASCADE,
    code VARCHAR(20) NOT NULL,
    label VARCHAR(80) NOT NULL,
    color VARCHAR(20) NOT NULL DEFAULT '#64748b',
    weight FLOAT NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subjective_rubric_mark_test_code UNIQUE(subjective_test_id, code)
)
''',
        f'CREATE INDEX IF NOT EXISTS idx_subjective_rubric_marks_test_id ON "{schema}".subjective_rubric_marks(subjective_test_id)',
        (
            'COMMENT ON TABLE "{schema}".subjective_rubric_marks IS '
            "'Marcações configuráveis da rubrica (rótulo, sigla, cor, peso) por avaliação subjetiva'"
        ).format(schema=schema),
        f'ALTER TABLE "{schema}".subjective_results DROP CONSTRAINT IF EXISTS ck_subjective_result_value',
        f'ALTER TABLE "{schema}".subjective_results ALTER COLUMN value TYPE VARCHAR(50)',
        f'''
INSERT INTO "{schema}".subjective_rubric_marks
    (id, subjective_test_id, code, label, color, weight, sort_order)
SELECT
    md5(t.id || v.code),
    t.id,
    v.code,
    v.label,
    v.color,
    v.weight,
    v.sort_order
FROM "{schema}".subjective_tests t
CROSS JOIN (
    VALUES
        ('SIM', 'Sim', '#22c55e', 1.0::float, 0),
        ('PARCIAL', 'Parcial', '#eab308', 0.5::float, 1),
        ('NAO', 'Não', '#ef4444', 0.0::float, 2),
        ('BRANCO', 'Branco', '#94a3b8', 0.0::float, 3)
) AS v(code, label, color, weight, sort_order)
WHERE NOT EXISTS (
    SELECT 1 FROM "{schema}".subjective_rubric_marks m
    WHERE m.subjective_test_id = t.id
)
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
