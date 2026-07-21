"""
Migration 0005: Nova entidade de avaliação subjetiva (subjective_tests / subjective_questions)
em cada schema city_xxx, substituindo o desenho anterior (que usava tenant.test + public.question).

Avaliação subjetiva agora é separada de test/question: a prova é física/impressa e fica
fora do sistema — só a estrutura (quantidade de questões, código e habilidade digitada
livremente por questão) é cadastrada. A correção continua manual, célula a célula
(aluno x questão), com a rubrica SIM/PARCIAL/NAO/BRANCO.

Esta migração:
1. Cria "{schema}".subjective_tests e "{schema}".subjective_questions.
2. Recria "{schema}".subjective_results e "{schema}".subjective_presences apontando para
   subjective_tests/subjective_questions (em vez de test/question). Como a funcionalidade
   ainda não foi liberada para uso (0004 só criou a estrutura anterior, sem dados reais
   de correção lançados), as tabelas antigas são dropadas e recriadas — não há dados a
   migrar. Se já houver lançamentos reais em algum ambiente, faça backup antes de rodar.

Idempotente para as tabelas novas (CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS).
O DROP TABLE das tabelas antigas usa IF EXISTS, então pode ser executado novamente sem erro.
"""

import os
import sys
import logging
from datetime import datetime
from typing import List

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

log_filename = f'migration_0005_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
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
        # Tabelas antigas (desenho anterior, baseado em tenant.test/public.question).
        f'DROP TABLE IF EXISTS "{schema}".subjective_results',
        f'DROP TABLE IF EXISTS "{schema}".subjective_presences',
        f'''
CREATE TABLE IF NOT EXISTS "{schema}".subjective_tests (
    id VARCHAR PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    test_type VARCHAR(50) DEFAULT 'Diagnóstica',
    subject_id VARCHAR NOT NULL REFERENCES public.subject(id),
    grade_id UUID NOT NULL REFERENCES public.grade(id),
    application_date DATE,
    municipalities JSON,
    schools JSON,
    classes JSON,
    status VARCHAR(20) DEFAULT 'pendente',
    created_by VARCHAR REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shadow_test_id VARCHAR REFERENCES "{schema}".test(id)
)''',
        f'''CREATE INDEX IF NOT EXISTS idx_subjective_tests_created_by ON "{schema}".subjective_tests(created_by)''',
        (
            'COMMENT ON TABLE "{schema}".subjective_tests IS '
            "'Avaliação subjetiva (cartão-resposta manual): só a estrutura é cadastrada, a prova física fica fora do sistema'"
        ).format(schema=schema),
        f'''
CREATE TABLE IF NOT EXISTS "{schema}".subjective_questions (
    id VARCHAR PRIMARY KEY,
    subjective_test_id VARCHAR NOT NULL REFERENCES "{schema}".subjective_tests(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    code VARCHAR(50),
    skill_description VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subjective_question_test_number UNIQUE(subjective_test_id, number)
)''',
        f'''CREATE INDEX IF NOT EXISTS idx_subjective_questions_test_id ON "{schema}".subjective_questions(subjective_test_id)''',
        (
            'COMMENT ON TABLE "{schema}".subjective_questions IS '
            "'Estrutura da questão da avaliação subjetiva: número, código e habilidade digitada livremente'"
        ).format(schema=schema),
        f'''
CREATE TABLE IF NOT EXISTS "{schema}".subjective_results (
    id VARCHAR PRIMARY KEY,
    subjective_test_id VARCHAR NOT NULL REFERENCES "{schema}".subjective_tests(id) ON DELETE CASCADE,
    subjective_question_id VARCHAR NOT NULL REFERENCES "{schema}".subjective_questions(id) ON DELETE CASCADE,
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    value VARCHAR(10) NOT NULL,
    corrected_by VARCHAR REFERENCES public.users(id),
    corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subjective_result_test_question_student UNIQUE(subjective_test_id, subjective_question_id, student_id),
    CONSTRAINT ck_subjective_result_value CHECK (value IN ('SIM', 'PARCIAL', 'NAO', 'BRANCO'))
)''',
        f'''CREATE INDEX IF NOT EXISTS idx_subjective_results_test_id ON "{schema}".subjective_results(subjective_test_id)''',
        f'''CREATE INDEX IF NOT EXISTS idx_subjective_results_student_id ON "{schema}".subjective_results(student_id)''',
        (
            'COMMENT ON TABLE "{schema}".subjective_results IS '
            "'Rubrica de correção manual (SIM/PARCIAL/NAO/BRANCO) da avaliação subjetiva'"
        ).format(schema=schema),
        f'''
CREATE TABLE IF NOT EXISTS "{schema}".subjective_presences (
    id VARCHAR PRIMARY KEY,
    subjective_test_id VARCHAR NOT NULL REFERENCES "{schema}".subjective_tests(id) ON DELETE CASCADE,
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    present BOOLEAN NOT NULL DEFAULT true,
    updated_by VARCHAR REFERENCES public.users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subjective_presence_test_student UNIQUE(subjective_test_id, student_id)
)''',
        f'''CREATE INDEX IF NOT EXISTS idx_subjective_presences_test_id ON "{schema}".subjective_presences(subjective_test_id)''',
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
                logger.info('OK: %s.subjective_tests / subjective_questions / subjective_results / subjective_presences', schema)
            except Exception as e:
                logger.error('Falha em %s: %s', schema, e, exc_info=True)
                raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    run_migration(dry_run=dry)
