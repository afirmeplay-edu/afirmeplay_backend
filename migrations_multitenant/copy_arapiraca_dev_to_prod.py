# -*- coding: utf-8 -*-
"""
Copia dados de Arapiraca de afirmeplay_dev -> afirmeplay_prod (aditivo).

- Origem: city schema do dev (city_id 5ea276c6-...)
- Destino: city schema do prod (city_id 716e7fd3-...)
- Não apaga nada em nenhum banco.
- Usuários com e-mail já existente no prod: remapeia user_id/student_id.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import psycopg2
from psycopg2.extras import execute_batch

DEV_CITY = "5ea276c6-4b81-4c95-a0a8-7f318e992c11"
PROD_CITY = "716e7fd3-c4ef-47c3-b5f7-f2f583267fcc"
DEV_SCHEMA = "city_5ea276c6_4b81_4c95_a0a8_7f318e992c11"
PROD_SCHEMA = "city_716e7fd3_c4ef_47c3_b5f7_f2f583267fcc"

SOURCE_DATABASE_URL = os.getenv(
    "SOURCE_DATABASE_URL",
    "postgresql://postgres:devpass@147.79.87.213:15432/afirmeplay_dev",
)
DEST_DATABASE_URL = os.getenv(
    "DEST_DATABASE_URL",
    "postgresql://postgres:devpass@147.79.87.213:15432/afirmeplay_prod",
)

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"copy_arapiraca_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

SKIP_TABLES = set()
SKIP_STUDENT_IDS: Set[str] = set()


def build_id_maps(source_conn, dest_conn) -> Tuple[Dict[str, str], Dict[str, str]]:
    with source_conn.cursor() as cur:
        cur.execute("SELECT id, email FROM public.users WHERE city_id = %s", (DEV_CITY,))
        dev_users = cur.fetchall()
    with dest_conn.cursor() as cur:
        cur.execute("SELECT id, email FROM public.users WHERE email IS NOT NULL")
        prod_by_email = {r[1]: r[0] for r in cur.fetchall() if r[1]}

    user_map: Dict[str, str] = {}
    for uid, email in dev_users:
        if email and email in prod_by_email:
            user_map[uid] = prod_by_email[email]

    with source_conn.cursor() as cur:
        cur.execute(f'SELECT id, user_id FROM "{DEV_SCHEMA}".student')
        dev_students = cur.fetchall()
    with dest_conn.cursor() as cur:
        cur.execute(f'SELECT id, user_id FROM "{PROD_SCHEMA}".student')
        prod_by_user = {r[1]: r[0] for r in cur.fetchall() if r[1]}

    student_map: Dict[str, str] = {}
    global SKIP_STUDENT_IDS
    for sid, uid in dev_students:
        if uid in user_map and user_map[uid] in prod_by_user:
            student_map[sid] = prod_by_user[user_map[uid]]
            SKIP_STUDENT_IDS.add(sid)

    logger.info("Mapeamentos: user=%d student=%d (students skip copy=%d)", len(user_map), len(student_map), len(SKIP_STUDENT_IDS))
    return user_map, student_map


def get_tables_with_data(conn, schema: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name",
            (schema,),
        )
        tables = [r[0] for r in cur.fetchall()]
        for t in tables:
            cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{t}"')
            n = cur.fetchone()[0]
            if n:
                counts[t] = n
    return counts


def topo_sort_tables(conn, schema: str, tables: List[str]) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tc.table_name, ccu.table_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = %s AND ccu.table_schema = %s
            """,
            (schema, schema),
        )
        deps = defaultdict(set)
        for child, parent in cur.fetchall():
            if child in tables and parent in tables and child != parent:
                deps[child].add(parent)

    in_degree = {t: 0 for t in tables}
    graph = defaultdict(list)
    for child, parents in deps.items():
        for p in parents:
            graph[p].append(child)
            in_degree[child] += 1

    queue = deque(sorted(t for t in tables if in_degree[t] == 0))
    order: List[str] = []
    while queue:
        t = queue.popleft()
        order.append(t)
        for child in sorted(graph[t]):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    remaining = [t for t in tables if t not in order]
    return order + sorted(remaining)


def get_columns(conn, schema: str, table: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        return [r[0] for r in cur.fetchall()]


def get_json_columns(conn, schema: str, table: str) -> Set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
              AND data_type IN ('json', 'jsonb')
            """,
            (schema, table),
        )
        return {r[0] for r in cur.fetchall()}


USER_ID_COLUMNS = {
    "user_id",
    "created_by",
    "created_by_user_id",
    "last_modified_by",
    "approved_by",
    "owner_user_id",
}


def transform_value(col: str, val: Any, user_map: Dict[str, str], student_map: Dict[str, str]) -> Any:
    if val is None:
        return None
    if col in ("city_id", "municipality_id") and str(val) == DEV_CITY:
        return PROD_CITY
    if col in USER_ID_COLUMNS and str(val) in user_map:
        return user_map[str(val)]
    if col == "student_id" and str(val) in student_map:
        return student_map[str(val)]
    return val


def copy_public_questions(
    source_conn,
    dest_conn,
    user_map: Dict[str, str],
    question_ids: List[str],
    dry_run: bool,
) -> int:
    if not question_ids:
        return 0

    with dest_conn.cursor() as cur:
        cur.execute("SELECT id FROM public.question WHERE id = ANY(%s)", (question_ids,))
        existing = {r[0] for r in cur.fetchall()}
    missing = [q for q in question_ids if q not in existing]
    if not missing:
        logger.info("public.question: nenhuma questão faltando")
        return 0

    with source_conn.cursor() as cur:
        cur.execute("SELECT * FROM public.question WHERE id = ANY(%s)", (missing,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    dest_cols = set(get_columns(dest_conn, "public", "question"))
    keep = [c for c in cols if c in dest_cols]
    indices = [cols.index(c) for c in keep]
    json_cols = get_json_columns(dest_conn, "public", "question")
    user_cols = USER_ID_COLUMNS

    to_insert = []
    for row in rows:
        new_row = []
        for c, i in zip(keep, indices):
            v = row[i]
            if c == "owner_city_id" and str(v) == DEV_CITY:
                v = PROD_CITY
            elif c in user_cols and v and str(v) in user_map:
                v = user_map[str(v)]
            elif c in json_cols and isinstance(v, (list, dict)):
                v = json.dumps(v, default=str)
            new_row.append(v)
        to_insert.append(tuple(new_row))

    logger.info("public.question: %d novas (de %d usadas no teste)", len(to_insert), len(question_ids))
    if dry_run or not to_insert:
        return len(to_insert)

    placeholders = ", ".join("%s" for _ in keep)
    col_sql = ", ".join(f'"{c}"' for c in keep)
    sql = f'INSERT INTO public.question ({col_sql}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING'
    with dest_conn.cursor() as cur:
        execute_batch(cur, sql, to_insert, page_size=200)
    return len(to_insert)


def get_test_question_ids(source_conn) -> List[str]:
    with source_conn.cursor() as cur:
        cur.execute(f'SELECT DISTINCT question_id::text FROM "{DEV_SCHEMA}".test_questions')
        return [r[0] for r in cur.fetchall() if r[0]]


def copy_public_users(
    source_conn,
    dest_conn,
    user_map: Dict[str, str],
    dry_run: bool,
) -> int:
    with source_conn.cursor() as cur:
        cur.execute("SELECT * FROM public.users WHERE city_id = %s", (DEV_CITY,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    with dest_conn.cursor() as cur:
        cur.execute("SELECT email FROM public.users WHERE email IS NOT NULL")
        prod_emails = {r[0] for r in cur.fetchall() if r[0]}

    dest_cols = set(get_columns(dest_conn, "public", "users"))
    keep = [c for c in cols if c in dest_cols]
    indices = [cols.index(c) for c in keep]
    json_cols = get_json_columns(dest_conn, "public", "users")

    to_insert = []
    skipped_email = 0
    for row in rows:
        uid = str(row[cols.index("id")])
        email = row[cols.index("email")]
        if email and email in prod_emails:
            skipped_email += 1
            continue
        new_row = []
        for c, i in zip(keep, indices):
            v = row[i]
            if c == "city_id":
                v = PROD_CITY
            elif c in json_cols and isinstance(v, (list, dict)):
                v = json.dumps(v, default=str)
            new_row.append(v)
        to_insert.append(tuple(new_row))

    logger.info("public.users: %d novos, %d ignorados (e-mail já no prod)", len(to_insert), skipped_email)
    if dry_run or not to_insert:
        return len(to_insert)

    placeholders = ", ".join("%s" for _ in keep)
    col_sql = ", ".join(f'"{c}"' for c in keep)
    sql = f'INSERT INTO public.users ({col_sql}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING'
    with dest_conn.cursor() as cur:
        execute_batch(cur, sql, to_insert, page_size=200)
    return len(to_insert)


def copy_table(
    source_conn,
    dest_conn,
    table: str,
    user_map: Dict[str, str],
    student_map: Dict[str, str],
    dry_run: bool,
) -> Tuple[int, int]:
    if table == "student":
        filter_sql = f'SELECT * FROM "{DEV_SCHEMA}"."{table}" WHERE id NOT IN %s'
        params: Tuple[Any, ...] = (tuple(SKIP_STUDENT_IDS) if SKIP_STUDENT_IDS else ("00000000-0000-0000-0000-000000000000",),)
        if not SKIP_STUDENT_IDS:
            # sem skip: truque com uuid impossível
            pass
    else:
        filter_sql = f'SELECT * FROM "{DEV_SCHEMA}"."{table}"'
        params = ()

    with source_conn.cursor() as cur:
        if table == "student" and SKIP_STUDENT_IDS:
            cur.execute(filter_sql, params)
        else:
            cur.execute(filter_sql)
        rows = cur.fetchall()
        if not rows:
            return 0, 0
        src_cols = [d[0] for d in cur.description]

    dest_cols = set(get_columns(dest_conn, PROD_SCHEMA, table))
    keep = [c for c in src_cols if c in dest_cols]
    if not keep:
        logger.warning("  %s: sem colunas em comum", table)
        return 0, 0

    indices = [src_cols.index(c) for c in keep]
    json_cols = get_json_columns(dest_conn, PROD_SCHEMA, table)

    out_rows = []
    for row in rows:
        new_row = []
        for c, i in zip(keep, indices):
            v = transform_value(c, row[i], user_map, student_map)
            if c in json_cols and isinstance(v, (list, dict)):
                v = json.dumps(v, default=str)
            new_row.append(v)
        out_rows.append(tuple(new_row))

    logger.info("  %s: %d linhas a inserir", table, len(out_rows))
    if dry_run or not out_rows:
        return len(out_rows), 0

    placeholders = ", ".join("%s" for _ in keep)
    col_sql = ", ".join(f'"{c}"' for c in keep)
    sql = (
        f'INSERT INTO "{PROD_SCHEMA}"."{table}" ({col_sql}) '
        f"VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"
    )
    with dest_conn.cursor() as cur:
        execute_batch(cur, sql, out_rows, page_size=500)
    return len(out_rows), 0


def run(dry_run: bool = False) -> None:
    logger.info("=" * 60)
    logger.info("Migração Arapiraca dev -> prod (aditiva)")
    logger.info("Origem: %s / %s", SOURCE_DATABASE_URL.rsplit("/", 1)[-1], DEV_SCHEMA)
    logger.info("Destino: %s / %s", DEST_DATABASE_URL.rsplit("/", 1)[-1], PROD_SCHEMA)
    if dry_run:
        logger.info("[DRY RUN]")

    source = psycopg2.connect(SOURCE_DATABASE_URL)
    dest = psycopg2.connect(DEST_DATABASE_URL)
    source.set_session(readonly=True)
    dest.autocommit = True

    try:
        user_map, student_map = build_id_maps(source, dest)
        counts = get_tables_with_data(source, DEV_SCHEMA)
        order = topo_sort_tables(source, DEV_SCHEMA, list(counts.keys()))
        logger.info("Tabelas com dados: %d", len(order))

        if not dry_run:
            dest.autocommit = False

        copy_public_users(source, dest, user_map, dry_run)
        copy_public_questions(source, dest, user_map, get_test_question_ids(source), dry_run)
        total = 0
        for table in order:
            if table in SKIP_TABLES:
                continue
            try:
                n, _ = copy_table(source, dest, table, user_map, student_map, dry_run)
                total += n
            except psycopg2.Error as e:
                logger.error("Falha em %s: %s", table, e)
                if not dry_run:
                    dest.rollback()
                raise

        if not dry_run:
            dest.commit()
            logger.info("Commit OK")

        logger.info("Total linhas tenant processadas: %d", total)
        logger.info("Log: %s", log_file)
        logger.info("=" * 60)
    finally:
        source.close()
        dest.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
