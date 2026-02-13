# -*- coding: utf-8 -*-
"""
Migration 0002: Cópia de dados public → city_xxx (entre dois bancos)

Copia dados do schema public do banco de origem (devdb) para os schemas
city_<id> do banco de destino (afirmeplay_dev), filtrados por city_id.

- ORIGEM: SOURCE_DATABASE_URL (devdb) - somente leitura em public
- DESTINO: DEST_DATABASE_URL (afirmeplay_dev) - escrita em city_xxx

Uso:
  Definir no app/.env ou ambiente:
    SOURCE_DATABASE_URL=postgresql://user:pass@host:port/devdb
    DEST_DATABASE_URL=postgresql://user:pass@host:port/afirmeplay_dev

  Dry-run (só loga):
    python migrations_multitenant/0002_copy_city_data.py --dry-run

  Execução real:
    python migrations_multitenant/0002_copy_city_data.py

  Apenas uma cidade (UUID):
    python migrations_multitenant/0002_copy_city_data.py --city-id "9a2f95ed-9f70-4863-a5f1-1b6c6c262b0d"
"""

import os
import sys
import logging
import argparse
import uuid
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Set
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

# Carregar .env
for path in ('app/.env', '../app/.env', os.path.join(os.path.dirname(__file__), '..', 'app', '.env')):
    if os.path.exists(path):
        load_dotenv(path)
        break

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f'0002_copy_city_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

SOURCE_DATABASE_URL = os.getenv('SOURCE_DATABASE_URL')
DEST_DATABASE_URL = os.getenv('DEST_DATABASE_URL')


def city_id_to_schema_name(city_id: str) -> str:
    """Converte city_id (UUID com hífens) no nome do schema (underscores)."""
    return f"city_{str(city_id).replace('-', '_')}"


# Ordem das tabelas e SQL de seleção (parâmetro: city_id).
# SELECT deve ser executado no banco de ORIGEM (public).
# Tabelas que não existirem na origem são ignoradas (log + continue).
TABLE_COPY_CONFIG: List[Dict] = [
    # 1. Escola
    {"table": "school", "sql": "SELECT * FROM public.school WHERE city_id = %s"},
    # 2. Cursos da escola
    {"table": "school_course", "sql": """
        SELECT c.* FROM public.school_course c
        INNER JOIN public.school s ON c.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 3. Professores (vinculados a escolas da cidade)
    {"table": "teacher", "sql": """
        SELECT t.* FROM public.teacher t
        WHERE t.id IN (
            SELECT st.teacher_id FROM public.school_teacher st
            INNER JOIN public.school s ON st.school_id::text = s.id
            WHERE s.city_id = %s
        )
    """},
    # 4. Vínculo escola-professor
    {"table": "school_teacher", "sql": """
        SELECT st.* FROM public.school_teacher st
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 5. Turmas
    {"table": "class", "sql": """
        SELECT c.* FROM public.class c
        INNER JOIN public.school s ON c.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 6. Disciplinas da turma
    {"table": "class_subject", "sql": """
        SELECT cs.* FROM public.class_subject cs
        INNER JOIN public.class c ON cs.class_id::text = c.id::text
        INNER JOIN public.school s ON c.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 7. Vínculo professor-turma
    {"table": "teacher_class", "sql": """
        SELECT tc.* FROM public.teacher_class tc
        INNER JOIN public.class c ON tc.class_id::text = c.id::text
        INNER JOIN public.school s ON c.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 8. Alunos
    {"table": "student", "sql": """
        SELECT st.* FROM public.student st
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 9. school_managers (origem: public.manager com school_id; destino: school_managers)
    # Se public.school_managers existir na origem, copie normalmente; senão use manager (tratado no código).
    {"table": "school_managers", "sql": """
        SELECT m.id AS manager_id, m.school_id
        FROM public.manager m
        INNER JOIN public.school s ON m.school_id::text = s.id
        WHERE s.city_id = %s AND m.school_id IS NOT NULL
    """, "skip_if_no_rows": True, "special": "school_managers_from_manager", "on_conflict": "(manager_id, school_id, is_active)"},
    # 10. Avaliações (tests usados na cidade via class_test)
    # Inclui testes de class_test, student_test_olimpics e competições com inscrições na cidade
    {"table": "test", "sql": """
        SELECT t.* FROM public.test t
        WHERE t.id IN (
            SELECT ct.test_id FROM public.class_test ct
            INNER JOIN public.class c ON ct.class_id::text = c.id::text
            INNER JOIN public.school s ON c.school_id::text = s.id
            WHERE s.city_id = %s
        )
        OR t.id IN (
            SELECT sto.test_id FROM public.student_test_olimpics sto
            INNER JOIN public.student st ON sto.student_id = st.id
            INNER JOIN public.school s ON st.school_id::text = s.id
            WHERE s.city_id = %s
        )
        OR t.id IN (
            SELECT co.test_id FROM public.competitions co
            WHERE co.id IN (
                SELECT ce.competition_id FROM public.competition_enrollments ce
                INNER JOIN public.student st ON ce.student_id = st.id
                INNER JOIN public.school s ON st.school_id::text = s.id
                WHERE s.city_id = %s
            )
        )
    """, "params": "three_city_id"},
    # 11. Questões do teste (inclui class_test, student_test_olimpics e competições)
    {"table": "test_questions", "sql": """
        SELECT tq.* FROM public.test_questions tq
        WHERE tq.test_id IN (
            SELECT ct.test_id FROM public.class_test ct
            INNER JOIN public.class c ON ct.class_id::text = c.id::text
            INNER JOIN public.school s ON c.school_id::text = s.id
            WHERE s.city_id = %s
        )
        OR tq.test_id IN (
            SELECT sto.test_id FROM public.student_test_olimpics sto
            INNER JOIN public.student st ON sto.student_id = st.id
            INNER JOIN public.school s ON st.school_id::text = s.id
            WHERE s.city_id = %s
        )
        OR tq.test_id IN (
            SELECT co.test_id FROM public.competitions co
            WHERE co.id IN (
                SELECT ce.competition_id FROM public.competition_enrollments ce
                INNER JOIN public.student st ON ce.student_id = st.id
                INNER JOIN public.school s ON st.school_id::text = s.id
                WHERE s.city_id = %s
            )
        )
    """, "params": "three_city_id"},
    # 12. Aplicação teste-turma
    {"table": "class_test", "sql": """
        SELECT ct.* FROM public.class_test ct
        INNER JOIN public.class c ON ct.class_id::text = c.id::text
        INNER JOIN public.school s ON c.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 13. Inscrições olimpíadas
    {"table": "student_test_olimpics", "sql": """
        SELECT sto.* FROM public.student_test_olimpics sto
        INNER JOIN public.student st ON sto.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 14. Respostas dos alunos
    {"table": "student_answers", "sql": """
        SELECT sa.* FROM public.student_answers sa
        INNER JOIN public.student st ON sa.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 15. Sessões de prova
    {"table": "test_sessions", "sql": """
        SELECT ts.* FROM public.test_sessions ts
        INNER JOIN public.student st ON ts.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 16. Resultados de avaliação
    {"table": "evaluation_results", "sql": """
        SELECT er.* FROM public.evaluation_results er
        INNER JOIN public.student st ON er.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 17. Formulários físicos
    {"table": "physical_test_forms", "sql": """
        SELECT ptf.* FROM public.physical_test_forms ptf
        INNER JOIN public.student st ON ptf.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 18. Respostas formulário físico
    {"table": "physical_test_answers", "sql": """
        SELECT pta.* FROM public.physical_test_answers pta
        INNER JOIN public.physical_test_forms ptf ON pta.physical_form_id = ptf.id
        INNER JOIN public.student st ON ptf.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 19. Coordenadas de formulário
    {"table": "form_coordinates", "sql": """
        SELECT fc.* FROM public.form_coordinates fc
        INNER JOIN public.student st ON fc.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 20. Gabaritos cartão resposta
    {"table": "answer_sheet_gabaritos", "sql": """
        SELECT g.* FROM public.answer_sheet_gabaritos g
        INNER JOIN public.school s ON g.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 21. Resultados cartão resposta
    {"table": "answer_sheet_results", "sql": """
        SELECT r.* FROM public.answer_sheet_results r
        INNER JOIN public.student st ON r.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 22. Jobs de correção em lote (por test_id usado na cidade)
    {"table": "batch_correction_jobs", "sql": """
        SELECT b.* FROM public.batch_correction_jobs b
        WHERE b.test_id IN (
            SELECT ct.test_id FROM public.class_test ct
            INNER JOIN public.class c ON ct.class_id::text = c.id::text
            INNER JOIN public.school s ON c.school_id::text = s.id
            WHERE s.city_id = %s
        )
    """},
    # 23. Cache relatórios
    {"table": "report_aggregates", "sql": """
        SELECT ra.* FROM public.report_aggregates ra
        WHERE ra.test_id IN (
            SELECT ct.test_id FROM public.class_test ct
            INNER JOIN public.class c ON ct.class_id::text = c.id::text
            INNER JOIN public.school s ON c.school_id::text = s.id
            WHERE s.city_id = %s
        )
    """},
    # 24. Jogos (criados por usuários da cidade ou vinculados a turmas da cidade)
    {"table": "games", "sql": """
        SELECT g.* FROM public.games g
        WHERE g.id IN (
            SELECT gc.game_id FROM public.game_classes gc
            INNER JOIN public.class c ON gc.class_id::text = c.id::text
            INNER JOIN public.school s ON c.school_id::text = s.id
            WHERE s.city_id = %s
        )
    """},
    # 25. Jogos por turma
    {"table": "game_classes", "sql": """
        SELECT gc.* FROM public.game_classes gc
        INNER JOIN public.class c ON gc.class_id::text = c.id::text
        INNER JOIN public.school s ON c.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # 26. Eventos de calendário (por municipality_id ou school_id)
    {"table": "calendar_events", "sql": """
        SELECT ce.* FROM public.calendar_events ce
        WHERE ce.municipality_id = %s OR ce.school_id IN (
            SELECT id FROM public.school WHERE city_id = %s
        )
    """, "params": "two_city_id"},  # passar city_id duas vezes
    # 27–28. Alvos e usuários de eventos (após calendar_events)
    {"table": "calendar_event_targets", "sql": """
        SELECT cet.* FROM public.calendar_event_targets cet
        INNER JOIN public.calendar_events ce ON cet.event_id = ce.id
        WHERE ce.municipality_id = %s OR ce.school_id IN (
            SELECT id FROM public.school WHERE city_id = %s
        )
    """, "params": "two_city_id"},
    {"table": "calendar_event_users", "sql": """
        SELECT ceu.* FROM public.calendar_event_users ceu
        INNER JOIN public.calendar_events ce ON ceu.event_id = ce.id
        WHERE ce.municipality_id = %s OR ce.school_id IN (
            SELECT id FROM public.school WHERE city_id = %s
        )
    """, "params": "two_city_id"},
    # 29. Competições (por test em class_test OU por inscrições de alunos da cidade)
    {"table": "competitions", "sql": """
        SELECT co.* FROM public.competitions co
        WHERE co.test_id IN (
            SELECT ct.test_id FROM public.class_test ct
            INNER JOIN public.class c ON ct.class_id::text = c.id::text
            INNER JOIN public.school s ON c.school_id::text = s.id
            WHERE s.city_id = %s
        )
        OR co.id IN (
            SELECT ce.competition_id FROM public.competition_enrollments ce
            INNER JOIN public.student st ON ce.student_id = st.id
            INNER JOIN public.school s ON st.school_id::text = s.id
            WHERE s.city_id = %s
        )
    """, "params": "two_city_id"},
    {"table": "competition_enrollments", "sql": """
        SELECT ce.* FROM public.competition_enrollments ce
        INNER JOIN public.student st ON ce.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    {"table": "competition_results", "sql": """
        SELECT cr.* FROM public.competition_results cr
        INNER JOIN public.student st ON cr.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    {"table": "competition_rewards", "sql": """
        SELECT cr.* FROM public.competition_rewards cr
        INNER JOIN public.student st ON cr.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    {"table": "competition_ranking_payouts", "sql": """
        SELECT crp.* FROM public.competition_ranking_payouts crp
        INNER JOIN public.student st ON crp.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # Formulários socioeconômicos (forms podem ter selected_schools; filtrar por escola na cidade)
    {"table": "forms", "sql": """
        SELECT f.* FROM public.forms f
        WHERE f.id IN (
            SELECT fr.form_id FROM public.form_recipients fr
            INNER JOIN public.school s ON fr.school_id::text = s.id
            WHERE s.city_id = %s
        ) OR f.created_by IN (
            SELECT u.id FROM public.users u WHERE u.city_id = %s
        )
    """, "params": "two_city_id"},
    {"table": "form_questions", "sql": """
        SELECT fq.* FROM public.form_questions fq
        INNER JOIN public.forms f ON fq.form_id = f.id
        WHERE f.id IN (
            SELECT fr.form_id FROM public.form_recipients fr
            INNER JOIN public.school s ON fr.school_id::text = s.id
            WHERE s.city_id = %s
        )
    """},
    {"table": "form_recipients", "sql": """
        SELECT fr.* FROM public.form_recipients fr
        INNER JOIN public.school s ON fr.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    {"table": "form_responses", "sql": """
        SELECT fresp.* FROM public.form_responses fresp
        WHERE fresp.recipient_id IN (
            SELECT fr.id FROM public.form_recipients fr
            INNER JOIN public.school s ON fr.school_id::text = s.id
            WHERE s.city_id = %s
        )
    """},
    {"table": "form_result_cache", "sql": """
        SELECT fc.* FROM public.form_result_cache fc
        WHERE fc.form_id IN (
            SELECT fr.form_id FROM public.form_recipients fr
            INNER JOIN public.school s ON fr.school_id::text = s.id
            WHERE s.city_id = %s
        )
    """},
    # Play TV / plantão
    {"table": "play_tv_video_schools", "sql": """
        SELECT pv.* FROM public.play_tv_video_schools pv
        INNER JOIN public.school s ON pv.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    {"table": "play_tv_video_classes", "sql": """
        SELECT pvc.* FROM public.play_tv_video_classes pvc
        INNER JOIN public.class c ON pvc.class_id::text = c.id::text
        INNER JOIN public.school s ON c.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    {"table": "plantao_schools", "sql": """
        SELECT ps.* FROM public.plantao_schools ps
        INNER JOIN public.school s ON ps.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # Certificados
    {"table": "certificate_templates", "sql": """
        SELECT ct.* FROM public.certificate_templates ct
        WHERE ct.evaluation_id IN (
            SELECT t.id FROM public.test t
            WHERE t.id IN (
                SELECT ct2.test_id FROM public.class_test ct2
                INNER JOIN public.class c ON ct2.class_id::text = c.id::text
                INNER JOIN public.school s ON c.school_id::text = s.id
                WHERE s.city_id = %s
            )
        )
    """},
    {"table": "certificates", "sql": """
        SELECT cert.* FROM public.certificates cert
        INNER JOIN public.student st ON cert.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # Moedas
    {"table": "student_coins", "sql": """
        SELECT sc.* FROM public.student_coins sc
        INNER JOIN public.student st ON sc.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    {"table": "coin_transactions", "sql": """
        SELECT ct.* FROM public.coin_transactions ct
        INNER JOIN public.student st ON ct.student_id = st.id
        INNER JOIN public.school s ON st.school_id::text = s.id
        WHERE s.city_id = %s
    """},
    # Log de senhas
    {"table": "student_password_log", "sql": """
        SELECT spl.* FROM public.student_password_log spl
        WHERE spl.city_id = %s
        AND spl.student_id IN (
            SELECT st.id FROM public.student st
            INNER JOIN public.school s ON st.school_id::text = s.id
            WHERE s.city_id = %s
        )
    """, "params": "two_city_id"},
]


def table_exists(conn, schema: str, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        """, (schema, table))
        return cur.fetchone() is not None


def get_dest_columns(conn, schema: str, table: str) -> Set[str]:
    """Retorna nomes de colunas que existem no destino (para inserir só colunas existentes)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))
        return {row[0] for row in cur.fetchall()}


def get_dest_json_columns(conn, schema: str, table: str) -> Set[str]:
    """Retorna nomes de colunas que são json/jsonb no destino (para converter array/object da origem)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            AND data_type IN ('json', 'jsonb')
        """, (schema, table))
        return {row[0] for row in cur.fetchall()}


def copy_table(
    source_conn,
    dest_conn,
    schema_name: str,
    table_name: str,
    select_sql: str,
    params: Tuple,
    dry_run: bool,
    skip_if_no_rows: bool = False,
    special: Optional[str] = None,
    on_conflict_columns: Optional[str] = None,
) -> Tuple[Optional[int], List[str]]:
    """Lê da origem (public) e insere no destino (schema city_xxx). Retorna (linhas_inseridas ou None, colunas_omitidas_no_destino)."""
    if dry_run:
        logger.info(f"  [DRY RUN] Copiando public.{table_name} -> {schema_name}.{table_name}")
        return (0, [])
    try:
        with source_conn.cursor() as src_cur:
            src_cur.execute(select_sql, params)
            rows = src_cur.fetchall()
            if not rows:
                if skip_if_no_rows:
                    return (0, [])
                logger.debug(f"  {table_name}: 0 linhas (ok)")
                return (0, [])
            col_names = [d[0] for d in src_cur.description]
    except psycopg2.Error as e:
        if e.pgcode == '42P01':  # undefined_table
            logger.warning(f"  Tabela public.{table_name} não existe na origem; pulando.")
            return (None, [])
        raise

    # Destino: verificar se tabela existe
    if not table_exists(dest_conn, schema_name, table_name):
        logger.warning(f"  Tabela {schema_name}.{table_name} não existe no destino; pulando.")
        return (None, [])

    # Caso especial: school_managers a partir de manager (origem não tem tabela school_managers)
    if special == "school_managers_from_manager":
        # rows = (manager_id, school_id); destino precisa: id, manager_id, school_id, role, started_at, ended_at, is_active, created_at, updated_at
        now = datetime.utcnow()
        full_rows = [
            (str(uuid.uuid4()), r[0], r[1], None, now, None, True, now, now)
            for r in rows
        ]
        col_names = ["id", "manager_id", "school_id", "role", "started_at", "ended_at", "is_active", "created_at", "updated_at"]
        rows = full_rows

    # Inserir apenas colunas que existem no destino (origem pode ter colunas a mais, ex.: minio_url)
    dest_columns = get_dest_columns(dest_conn, schema_name, table_name)
    indices_keep = [i for i in range(len(col_names)) if col_names[i] in dest_columns]
    skipped_cols = [col_names[i] for i in range(len(col_names)) if col_names[i] not in dest_columns]
    if skipped_cols:
        logger.debug(f"  {table_name}: colunas omitidas (não existem no destino): {skipped_cols}")
    col_names = [col_names[i] for i in indices_keep]
    rows = [tuple(r[i] for i in indices_keep) for r in rows]
    if not col_names:
        logger.warning(f"  {table_name}: nenhuma coluna em comum com o destino; pulando.")
        return (None, list(skipped_cols))

    # Colunas JSON/JSONB no destino: converter list/dict da origem (ex.: text[] -> json) para string JSON
    json_cols = get_dest_json_columns(dest_conn, schema_name, table_name)
    if json_cols:
        col_indexes_json = [i for i, name in enumerate(col_names) if name in json_cols]
        def row_for_dest(row_tuple):
            row_list = list(row_tuple)
            for i in col_indexes_json:
                v = row_list[i]
                if isinstance(v, (list, dict)):
                    row_list[i] = json.dumps(v, default=str)
            return tuple(row_list)
        rows = [row_for_dest(r) for r in rows]

    cols = ", ".join(f'"{c}"' for c in col_names)
    placeholders = ", ".join("%s" for _ in col_names)
    # ON CONFLICT DO NOTHING permite reexecutar o script sem falha por chave duplicada
    if on_conflict_columns:
        on_conflict = f' ON CONFLICT {on_conflict_columns} DO NOTHING'
    elif 'id' in col_names:
        on_conflict = ' ON CONFLICT (id) DO NOTHING'
    else:
        on_conflict = ''
    insert_sql = f'INSERT INTO "{schema_name}"."{table_name}" ({cols}) VALUES ({placeholders}){on_conflict}'

    try:
        with dest_conn.cursor() as dest_cur:
            execute_batch(dest_cur, insert_sql, rows, page_size=500)
        count = len(rows)
        logger.info(f"  {table_name}: {count} linhas processadas (inseridas ou já existentes).")
        return (count, skipped_cols)
    except psycopg2.Error as e:
        logger.error(f"  Erro ao inserir em {schema_name}.{table_name}: {e}")
        raise


def listar_colunas_faltando_no_destino(missing_by_table: Dict[str, Set[str]]) -> None:
    """Escreve no log o resumo das colunas que existem na origem mas não no destino."""
    if not missing_by_table:
        return
    logger.info("")
    logger.info("--- Colunas que existem na ORIGEM mas NÃO no DESTINO (omitidas na cópia) ---")
    for table in sorted(missing_by_table.keys()):
        cols = sorted(missing_by_table[table])
        logger.info(f"  {table}: {', '.join(cols)}")
    logger.info("--- Fim da lista ---")


def run_migration(dry_run: bool = False, city_id_filter: Optional[str] = None):
    if not SOURCE_DATABASE_URL or not DEST_DATABASE_URL:
        logger.error("Defina SOURCE_DATABASE_URL e DEST_DATABASE_URL (ex.: no app/.env)")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("0002: Cópia de dados public (origem) -> city_xxx (destino)")
    logger.info("=" * 60)
    logger.info(f"Origem (somente leitura): {SOURCE_DATABASE_URL.split('@')[-1] if '@' in SOURCE_DATABASE_URL else '...'}")
    logger.info(f"Destino: {DEST_DATABASE_URL.split('@')[-1] if '@' in DEST_DATABASE_URL else '...'}")
    if dry_run:
        logger.info("[DRY RUN] Nenhum dado será alterado.")
    if city_id_filter:
        logger.info(f"Filtro: apenas city_id = {city_id_filter}")

    source_conn = psycopg2.connect(SOURCE_DATABASE_URL)
    dest_conn = psycopg2.connect(DEST_DATABASE_URL)
    source_conn.set_session(readonly=True)
    total_copied = 0
    errors = []
    # Acumula colunas que existem na origem mas não no destino (por tabela)
    colunas_faltando_no_destino: Dict[str, Set[str]] = {}

    try:
        with source_conn.cursor() as cur:
            cur.execute("SELECT id, name, state FROM public.city ORDER BY name")
            cities = [{"id": r[0], "name": r[1], "state": r[2]} for r in cur.fetchall()]
        if city_id_filter:
            cities = [c for c in cities if str(c["id"]) == str(city_id_filter)]
            if not cities:
                logger.error(f"Nenhuma cidade encontrada com id = {city_id_filter}")
                sys.exit(1)
        logger.info(f"Cidades a processar: {len(cities)}")

        for city in cities:
            cid = city["id"]
            schema_name = city_id_to_schema_name(cid)
            logger.info(f"\n--- Cidade: {city['name']} ({city['state']}) | schema = {schema_name} ---")

            if not dry_run and not table_exists(dest_conn, schema_name, "school"):
                logger.warning(f"Schema {schema_name} não possui tabela school (não criado pelo 0001?). Pulando cidade.")
                continue

            dest_conn.rollback()
            dest_conn.autocommit = False
            try:
                for cfg in TABLE_COPY_CONFIG:
                    table_name = cfg["table"]
                    sql = cfg["sql"].strip()
                    params_mode = cfg.get("params", "one_city_id")
                    if params_mode == "three_city_id":
                        params = (cid, cid, cid)
                    elif params_mode == "two_city_id":
                        params = (cid, cid)
                    else:
                        params = (cid,)
                    skip_no_rows = cfg.get("skip_if_no_rows", False)
                    special = cfg.get("special")
                    on_conflict_cols = cfg.get("on_conflict")
                    try:
                        n, skipped_cols = copy_table(
                            source_conn, dest_conn,
                            schema_name, table_name, sql, params,
                            dry_run=dry_run,
                            skip_if_no_rows=skip_no_rows,
                            special=special,
                            on_conflict_columns=on_conflict_cols,
                        )
                        if n is not None and n > 0:
                            total_copied += n
                        if skipped_cols:
                            colunas_faltando_no_destino.setdefault(table_name, set()).update(skipped_cols)
                    except Exception as e:
                        errors.append((city["name"], table_name, str(e)))
                        logger.exception(f"Erro em {schema_name}.{table_name}")
                        if not dry_run:
                            dest_conn.rollback()
                            raise
                if not dry_run:
                    dest_conn.commit()
            except Exception as e:
                dest_conn.rollback()
                errors.append((city["name"], "commit", str(e)))
                logger.error(f"Rollback na cidade {city['name']}: {e}")
                raise

        logger.info("\n" + "=" * 60)
        logger.info(f"Total de linhas copiadas: {total_copied}")
        if errors:
            logger.warning(f"Erros encontrados: {len(errors)}")
            for city_name, tbl, err in errors:
                logger.warning(f"  - {city_name} / {tbl}: {err}")
        listar_colunas_faltando_no_destino(colunas_faltando_no_destino)
        logger.info("=" * 60)
    finally:
        source_conn.close()
        dest_conn.close()


def main():
    parser = argparse.ArgumentParser(description="0002: Copiar dados public (devdb) -> city_xxx (afirmeplay_dev)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas simular (não escrever no destino)")
    parser.add_argument("--city-id", type=str, default=None, help="Processar apenas esta cidade (UUID)")
    args = parser.parse_args()
    run_migration(dry_run=args.dry_run, city_id_filter=args.city_id)


if __name__ == "__main__":
    main()
