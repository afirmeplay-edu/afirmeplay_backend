"""
Migration 0006: coluna grades (JSON) em answer_sheet_gabaritos + backfill.

Armazena séries aplicáveis ao gabarito: [{"id": "<uuid>", "name": "9º Ano"}, ...].
Backfill: se grade_id preenchido → 1 item; senão, séries distintas dos resultados.

Idempotente: ADD COLUMN IF NOT EXISTS.
"""

import json
import os
import sys
import logging
from datetime import datetime
from typing import List

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

log_filename = f'migration_0006_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
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
    return [
        f'''ALTER TABLE "{schema}".answer_sheet_gabaritos
            ADD COLUMN IF NOT EXISTS grades JSON''',
        (
            f'COMMENT ON COLUMN "{schema}".answer_sheet_gabaritos.grades IS '
            "'Séries aplicáveis ao gabarito: [{id, name}, ...]'"
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


def _column_exists(cursor, schema: str, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (schema, table, column),
    )
    return cursor.fetchone() is not None


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


def _grades_from_results(cursor, schema: str, gab_id: str) -> List[dict]:
    """
    Infere séries dos resultados.
    Preferência: grade_id_snapshot; fallback: student.class.grade_id
    (schemas antigos podem não ter grade_id_snapshot).
    """
    grades: List[dict] = []
    if not _table_exists(cursor, schema, "answer_sheet_results"):
        return grades

    if _column_exists(cursor, schema, "answer_sheet_results", "grade_id_snapshot"):
        cursor.execute(
            f'''
            SELECT r.grade_id_snapshot::text, MAX(gr.name) AS name
            FROM "{schema}".answer_sheet_results r
            LEFT JOIN public.grade gr ON gr.id = r.grade_id_snapshot
            WHERE r.gabarito_id = %s
              AND r.grade_id_snapshot IS NOT NULL
            GROUP BY r.grade_id_snapshot
            ORDER BY MAX(gr.name) NULLS LAST
            ''',
            (gab_id,),
        )
        for gid, gname in cursor.fetchall():
            if gid:
                grades.append({"id": gid, "name": (gname or "")})
        if grades:
            return grades

    # Fallback legado: série atual da turma do aluno
    if (
        _table_exists(cursor, schema, "student")
        and _table_exists(cursor, schema, "class")
    ):
        cursor.execute(
            f'''
            SELECT c.grade_id::text, MAX(gr.name) AS name
            FROM "{schema}".answer_sheet_results r
            JOIN "{schema}".student s ON s.id = r.student_id
            JOIN "{schema}".class c ON c.id = s.class_id
            LEFT JOIN public.grade gr ON gr.id = c.grade_id
            WHERE r.gabarito_id = %s
              AND c.grade_id IS NOT NULL
            GROUP BY c.grade_id
            ORDER BY MAX(gr.name) NULLS LAST
            ''',
            (gab_id,),
        )
        for gid, gname in cursor.fetchall():
            if gid:
                grades.append({"id": gid, "name": (gname or "")})
    return grades


def backfill_schema(cursor, schema: str) -> int:
    """Preenche grades a partir de grade_id ou snapshots dos resultados."""
    if not _table_exists(cursor, schema, "answer_sheet_gabaritos"):
        logger.warning("[%s] tabela answer_sheet_gabaritos ausente — pulando backfill", schema)
        return 0

    updated = 0
    cursor.execute(
        f'''
        SELECT id, grade_id::text, grade_name
        FROM "{schema}".answer_sheet_gabaritos
        WHERE grades IS NULL
           OR grades::text IN ('null', '[]', '')
        '''
    )
    rows = cursor.fetchall()
    for gab_id, grade_id, grade_name in rows:
        grades = []
        if grade_id:
            name = (grade_name or "").strip()
            if not name:
                cursor.execute(
                    "SELECT name FROM public.grade WHERE id::text = %s",
                    (grade_id,),
                )
                g = cursor.fetchone()
                name = (g[0] if g else "") or ""
            grades = [{"id": grade_id, "name": name}]
        else:
            grades = _grades_from_results(cursor, schema, gab_id)
        if not grades:
            continue
        grades_json = json.dumps(grades, ensure_ascii=False)
        if len(grades) == 1:
            cursor.execute(
                f'''
                UPDATE "{schema}".answer_sheet_gabaritos
                SET grades = %s::json,
                    grade_id = %s::uuid,
                    grade_name = %s
                WHERE id = %s
                ''',
                (grades_json, grades[0]["id"], grades[0]["name"] or None, gab_id),
            )
        else:
            cursor.execute(
                f'''
                UPDATE "{schema}".answer_sheet_gabaritos
                SET grades = %s::json,
                    grade_id = NULL,
                    grade_name = NULL
                WHERE id = %s
                ''',
                (grades_json, gab_id),
            )
        updated += 1
    return updated


def run_migration(dry_run: bool = False):
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    try:
        schemas = get_city_schemas(cursor)
        logger.info("Schemas city_*: %s", len(schemas))
        total_backfill = 0
        errors = 0
        for schema in schemas:
            try:
                for stmt in _ddl_for_schema(schema):
                    logger.info("[%s] %s", schema, stmt.strip().split("\n")[0][:80])
                    if not dry_run:
                        cursor.execute(stmt)
                if not dry_run:
                    n = backfill_schema(cursor, schema)
                    total_backfill += n
                    if n:
                        logger.info("[%s] backfill grades: %s gabarito(s)", schema, n)
            except Exception as exc:
                errors += 1
                logger.error("[%s] falha (continua nos demais): %s", schema, exc, exc_info=True)
        logger.info("Concluído. Backfill total: %s | erros: %s", total_backfill, errors)
        if errors:
            sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run_migration(dry_run=dry)
