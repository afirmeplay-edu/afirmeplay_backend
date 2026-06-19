# -*- coding: utf-8 -*-
"""
Consolida a prova duplicada de Arapiraca no prod:
- Mantém a prova original do prod (KEEP_TEST)
- Move resultados da prova importada do dev (DEV_TEST) para KEEP_TEST
- Remove a prova importada e vínculos órfãos

Não altera alunos, turmas, escolas.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime

import psycopg2

PROD_SCHEMA = "city_716e7fd3_c4ef_47c3_b5f7_f2f583267fcc"
DEV_TEST = "00f2fad9-f473-4332-a913-b879ebcf5741"  # importada do dev
KEEP_TEST = "b433c766-7297-4e3e-b330-02f437cdc7a6"  # original prod
DEV_CLASS_TEST = "18851681-4ebb-414f-959c-63ec370da615"
KEEP_CLASS_TEST = "030df1bb-d275-4778-ae9f-ff3f133a44e3"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:devpass@147.79.87.213:15432/afirmeplay_prod",
)

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"merge_arapiraca_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)
S = PROD_SCHEMA


def count(cur, sql: str, params=()) -> int:
    cur.execute(sql, params)
    return cur.fetchone()[0]


def run(dry_run: bool = False) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        logger.info("=" * 60)
        logger.info("Merge prova duplicada Arapiraca (prod)")
        logger.info("DEV_TEST (remover): %s", DEV_TEST)
        logger.info("KEEP_TEST (oficial): %s", KEEP_TEST)
        if dry_run:
            logger.info("[DRY RUN]")

        before_er_dev = count(cur, f'SELECT count(*) FROM "{S}".evaluation_results WHERE test_id = %s', (DEV_TEST,))
        before_er_keep = count(cur, f'SELECT count(*) FROM "{S}".evaluation_results WHERE test_id = %s', (KEEP_TEST,))
        logger.info("evaluation_results antes: keep=%d dev=%d", before_er_keep, before_er_dev)

        steps = [
            # 1. Remover formulários físicos duplicados (aluno já tem no KEEP)
            f"""
            DELETE FROM "{S}".physical_test_answers pta
            WHERE pta.physical_form_id IN (
                SELECT ptf.id FROM "{S}".physical_test_forms ptf
                WHERE ptf.test_id = '{DEV_TEST}'
                  AND ptf.student_id IN (
                    SELECT student_id FROM "{S}".physical_test_forms
                    WHERE test_id = '{KEEP_TEST}'
                  )
            )
            """,
            f"""
            DELETE FROM "{S}".physical_test_forms
            WHERE test_id = '{DEV_TEST}'
              AND student_id IN (
                SELECT student_id FROM "{S}".physical_test_forms
                WHERE test_id = '{KEEP_TEST}'
              )
            """,
            # 2. Remover sessões duplicadas (sem evaluation_results — verificado)
            f"""
            DELETE FROM "{S}".test_sessions
            WHERE test_id = '{DEV_TEST}'
              AND student_id IN (
                SELECT student_id FROM "{S}".test_sessions
                WHERE test_id = '{KEEP_TEST}'
              )
            """,
            # 3. Mover resultados para KEEP_TEST
            f'UPDATE "{S}".test_sessions SET test_id = %s WHERE test_id = %s',
            f'UPDATE "{S}".evaluation_results SET test_id = %s WHERE test_id = %s',
            f'UPDATE "{S}".student_answers SET test_id = %s WHERE test_id = %s',
            f"""
            UPDATE "{S}".physical_test_forms
            SET test_id = %s, class_test_id = %s
            WHERE test_id = %s
            """,
            f'UPDATE "{S}".form_coordinates SET test_id = %s WHERE test_id = %s',
            f'UPDATE "{S}".student_test_olimpics SET test_id = %s WHERE test_id = %s',
            # 4. Remover agregados/gabaritos duplicados da prova dev
            f'DELETE FROM "{S}".report_aggregates WHERE test_id = %s',
            f'DELETE FROM "{S}".answer_sheet_gabaritos WHERE test_id = %s',
            f'DELETE FROM "{S}".batch_correction_jobs WHERE test_id = %s',
            f'DELETE FROM "{S}".physical_test_zip WHERE test_id = %s',
            f'DELETE FROM "{S}".form_coordinates WHERE test_id = %s',
            f'DELETE FROM "{S}".certificates WHERE evaluation_id = %s',
            f'DELETE FROM "{S}".certificate_templates WHERE evaluation_id = %s',
            f'DELETE FROM "{S}".competitions WHERE test_id = %s',
            f'DELETE FROM "{S}".test_questions WHERE test_id = %s',
            f'DELETE FROM "{S}".class_test WHERE test_id = %s',
            f'DELETE FROM "{S}".test WHERE id = %s',
        ]

        params_map = {
            3: (KEEP_TEST, DEV_TEST),
            4: (KEEP_TEST, DEV_TEST),
            5: (KEEP_TEST, DEV_TEST),
            6: (KEEP_TEST, KEEP_CLASS_TEST, DEV_TEST),
            7: (KEEP_TEST, DEV_TEST),
            8: (KEEP_TEST, DEV_TEST),
            9: (DEV_TEST,),
            10: (DEV_TEST,),
            11: (DEV_TEST,),
            12: (DEV_TEST,),
            13: (DEV_TEST,),
            14: (DEV_TEST,),
            15: (DEV_TEST,),
            16: (DEV_TEST,),
            17: (DEV_TEST,),
            18: (DEV_TEST,),
            19: (DEV_TEST,),
        }

        labels = [
            "delete physical_test_answers (dup forms)",
            "delete physical_test_forms (dup students)",
            "delete test_sessions (dup students)",
            "update test_sessions.test_id",
            "update evaluation_results.test_id",
            "update student_answers.test_id",
            "update physical_test_forms.test_id + class_test_id",
            "update form_coordinates.test_id",
            "update student_test_olimpics.test_id",
            "delete report_aggregates",
            "delete answer_sheet_gabaritos",
            "delete batch_correction_jobs",
            "delete physical_test_zip",
            "delete form_coordinates (orphan)",
            "delete certificates",
            "delete certificate_templates",
            "delete competitions",
            "delete test_questions",
            "delete class_test",
            "delete test",
        ]

        for i, (sql, label) in enumerate(zip(steps, labels)):
            if dry_run:
                logger.info("[DRY RUN] %s", label)
                continue
            params = params_map.get(i, ())
            cur.execute(sql, params)
            logger.info("%s: %d linhas afetadas", label, cur.rowcount)

        if not dry_run:
            cur.execute(f'SELECT count(*) FROM "{S}".evaluation_results WHERE test_id = %s', (KEEP_TEST,))
            after_er = cur.fetchone()[0]
            cur.execute(f'SELECT count(*) FROM "{S}".test WHERE id = %s', (DEV_TEST,))
            dev_test_exists = cur.fetchone()[0]
            cur.execute(f'SELECT count(*) FROM "{S}".test')
            test_count = cur.fetchone()[0]
            conn.commit()
            logger.info("evaluation_results depois (KEEP): %d (esperado %d)", after_er, before_er_keep + before_er_dev)
            logger.info("prova dev ainda existe: %s | total provas: %d", bool(dev_test_exists), test_count)
            logger.info("Commit OK")
        else:
            conn.rollback()

        logger.info("Log: %s", log_file)
        logger.info("=" * 60)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
