"""
Migration 0004: Tabelas subjective_results e subjective_presences em cada schema city_xxx

Avaliação subjetiva (Test.evaluation_mode == 'subjective'): rubrica de correção manual
(SIM/PARCIAL/NAO/BRANCO) lançada pelo professor por aluno/questão, e presença do aluno
na aplicação. Não há resposta online do aluno nesse fluxo.

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

log_filename = f'migration_0004_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
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
CREATE TABLE IF NOT EXISTS "{schema}".subjective_results (
    id VARCHAR PRIMARY KEY,
    test_id VARCHAR NOT NULL REFERENCES "{schema}".test(id),
    question_id VARCHAR NOT NULL REFERENCES public.question(id),
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    value VARCHAR(10) NOT NULL,
    corrected_by VARCHAR REFERENCES public.users(id),
    corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subjective_result_test_question_student UNIQUE(test_id, question_id, student_id),
    CONSTRAINT ck_subjective_result_value CHECK (value IN ('SIM', 'PARCIAL', 'NAO', 'BRANCO'))
)''',
        f'''CREATE INDEX IF NOT EXISTS idx_subjective_results_test_id ON "{schema}".subjective_results(test_id)''',
        f'''CREATE INDEX IF NOT EXISTS idx_subjective_results_student_id ON "{schema}".subjective_results(student_id)''',
        (
            'COMMENT ON TABLE "{schema}".subjective_results IS '
            "'Rubrica de correção manual (SIM/PARCIAL/NAO/BRANCO) da avaliação subjetiva'"
        ).format(schema=schema),
        f'''
CREATE TABLE IF NOT EXISTS "{schema}".subjective_presences (
    id VARCHAR PRIMARY KEY,
    test_id VARCHAR NOT NULL REFERENCES "{schema}".test(id),
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    present BOOLEAN NOT NULL DEFAULT true,
    updated_by VARCHAR REFERENCES public.users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subjective_presence_test_student UNIQUE(test_id, student_id)
)''',
        f'''CREATE INDEX IF NOT EXISTS idx_subjective_presences_test_id ON "{schema}".subjective_presences(test_id)''',
        (
            'COMMENT ON TABLE "{schema}".subjective_presences IS '
            "'Presença do aluno na aplicação da avaliação subjetiva'"
        ).format(schema=schema),
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
        for schema in schemas:
            if dry_run:
                logger.info('[DRY RUN] Aplicaria DDL em %s', schema)
                continue
            try:
                for stmt in _ddl_for_schema(schema):
                    cursor.execute(stmt)
                logger.info('OK: %s.subjective_results / %s.subjective_presences', schema, schema)
            except Exception as e:
                logger.error('Falha em %s: %s', schema, e, exc_info=True)
                raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    run_migration(dry_run=dry)
