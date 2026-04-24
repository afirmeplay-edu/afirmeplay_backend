"""
Script para diagnosticar e (se necessário) mover uma `test_sessions` do schema `public`
para um schema de município `city_*`.

Motivação (bug típico):
- `evaluation_results` no tenant (city_*) tem FK para `test_sessions(id)` do mesmo schema.
- Se a sessão foi criada em `public.test_sessions` por engano, o insert em
  `city_*.evaluation_results` falha com ForeignKeyViolation.

Uso:
  # dry-run (apenas imprime diagnóstico)
  python scripts/fix_test_session_schema.py --session-id <uuid> --city-schema city_xxx --dry-run

  # executa a migração (transactional)
  python scripts/fix_test_session_schema.py --session-id <uuid> --city-schema city_xxx

Requisitos:
  - `DATABASE_URL` definido em `app/.env` (ou já exportado no ambiente).
  - Driver PostgreSQL: `psycopg2` ou `psycopg` instalado no ambiente Python.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Dict, Optional, Sequence, Tuple


def _read_env_file(path: str) -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    out: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f.readlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                out[k] = v
    return out


def _get_database_url() -> str:
    # 1) variável já exportada
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    # 2) app/.env na raiz do repo
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_path = os.path.join(repo_root, "app", ".env")
    vals = _read_env_file(env_path)
    url = vals.get("DATABASE_URL") or ""
    if not url:
        raise RuntimeError(
            "DATABASE_URL não encontrado. Defina a variável de ambiente DATABASE_URL "
            "ou crie `app/.env` com DATABASE_URL=postgresql://..."
        )
    return url


def _connect(database_url: str):
    # Preferir psycopg (v3) se existir; fallback para psycopg2.
    try:
        import psycopg  # type: ignore

        conn = psycopg.connect(database_url)
        conn.autocommit = False
        return conn, "psycopg"
    except Exception:
        pass

    try:
        import psycopg2  # type: ignore

        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        return conn, "psycopg2"
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Não foi possível conectar no Postgres. Instale `psycopg` (v3) ou `psycopg2`.\n"
            f"Erro: {e}"
        )


def _is_safe_city_schema(name: str) -> bool:
    # só permitir city_<uuid> com underscores
    return bool(re.fullmatch(r"city_[0-9a-fA-F]{8}_[0-9a-fA-F]{4}_[0-9a-fA-F]{4}_[0-9a-fA-F]{4}_[0-9a-fA-F]{12}", name))


def _fetch_one(cur, sql: str, params: Sequence[object]) -> Optional[Tuple]:
    cur.execute(sql, params)
    row = cur.fetchone()
    return row


def _fetch_columns(cur, schema: str) -> Sequence[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = 'test_sessions'
        ORDER BY ordinal_position
        """,
        (schema,),
    )
    return [r[0] for r in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-id", required=True, help="ID da sessão (test_sessions.id)")
    ap.add_argument("--city-schema", required=True, help="Schema do município, ex.: city_xxx")
    ap.add_argument("--dry-run", action="store_true", help="Não altera dados; apenas mostra diagnóstico")
    args = ap.parse_args()

    session_id = str(args.session_id).strip()
    city_schema = str(args.city_schema).strip()

    if not _is_safe_city_schema(city_schema):
        print(f"ERRO: city-schema inválido: {city_schema}", file=sys.stderr)
        return 2

    database_url = _get_database_url()
    conn, driver = _connect(database_url)
    print(f"Conectado via {driver}.")

    try:
        cur = conn.cursor()

        # existência da sessão em public e no tenant
        public_row = _fetch_one(
            cur,
            'SELECT id, student_id, test_id, started_at, actual_start_time, submitted_at, time_limit_minutes, status, '
            'total_questions, correct_answers, score, grade, manual_score, feedback, corrected_by, corrected_at, '
            'ip_address, user_agent, created_at, updated_at '
            "FROM public.test_sessions WHERE id = %s",
            (session_id,),
        )
        city_row = _fetch_one(
            cur,
            f'SELECT id FROM "{city_schema}".test_sessions WHERE id = %s',
            (session_id,),
        )

        print(f"public.test_sessions: {'ENCONTRADA' if public_row else 'não encontrada'}")
        print(f'{city_schema}.test_sessions: {"ENCONTRADA" if city_row else "não encontrada"}')

        if city_row:
            print("OK: sessão já está no schema do município; nada a fazer.")
            conn.rollback()
            return 0

        if not public_row:
            print("ERRO: sessão não encontrada nem em public nem no schema do município.", file=sys.stderr)
            conn.rollback()
            return 1

        if args.dry_run:
            print("DRY-RUN: iria copiar a sessão de public -> city e apagar de public.")
            conn.rollback()
            return 0

        # Validar compatibilidade de colunas entre os schemas (evita insert quebrado).
        public_cols = _fetch_columns(cur, "public")
        city_cols = _fetch_columns(cur, city_schema)
        common = [c for c in public_cols if c in city_cols]
        missing_in_city = [c for c in public_cols if c not in city_cols]

        if missing_in_city:
            print(
                "ERRO: colunas presentes em public.test_sessions mas ausentes no schema city. "
                f"Não é seguro migrar automaticamente: {missing_in_city}",
                file=sys.stderr,
            )
            conn.rollback()
            return 3

        # Montar INSERT apenas com colunas comuns (aqui common == public_cols).
        cols_sql = ", ".join([f'"{c}"' for c in common])
        placeholders = ", ".join(["%s"] * len(common))
        values = list(public_row)  # mesma ordem do SELECT fixo acima

        cur.execute(
            f'INSERT INTO "{city_schema}".test_sessions ({cols_sql}) VALUES ({placeholders})',
            values,
        )
        cur.execute("DELETE FROM public.test_sessions WHERE id = %s", (session_id,))

        conn.commit()
        print("OK: sessão migrada de public para o schema do município com sucesso.")
        return 0

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"ERRO: {e}", file=sys.stderr)
        return 10
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

