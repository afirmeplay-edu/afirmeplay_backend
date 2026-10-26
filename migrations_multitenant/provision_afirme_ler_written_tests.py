# -*- coding: utf-8 -*-
"""
Cria as tabelas da avaliação escrita do Afirme Ler nos schemas city_* JÁ EXISTENTES:
reading_written_test e reading_written_test_question (CREATE TABLE IF NOT EXISTS).

Não toca reading_evaluation nem as demais tabelas da fluência.
Municípios novos já recebem as tabelas pelo provisionamento (city_schema_service).

Padrão = SIMULAÇÃO: só lê o banco e mostra, por schema, o que seria criado.

Uso (na raiz do repositório):

  python migrations_multitenant/provision_afirme_ler_written_tests.py
  python migrations_multitenant/provision_afirme_ler_written_tests.py --execute
  python migrations_multitenant/provision_afirme_ler_written_tests.py --schema city_xxx --execute
  python migrations_multitenant/provision_afirme_ler_written_tests.py --rollback
  python migrations_multitenant/provision_afirme_ler_written_tests.py --rollback --execute

--rollback apaga as duas tabelas (e os dados delas) nos schemas escolhidos.

Requer DATABASE_URL em app/.env (ou no ambiente). DATABASE_URL_LEITURA não é usada.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(os.path.join(ROOT, "app", ".env"))

from app.afirme_ler.ddl import (  # noqa: E402
    WRITTEN_TEST_TABLES,
    get_afirme_ler_written_test_tables_ddl,
)


def _drop_ddl(schema: str) -> str:
    return (
        f'DROP TABLE IF EXISTS "{schema}".reading_written_test_question;\n'
        f'DROP TABLE IF EXISTS "{schema}".reading_written_test;\n'
    )


def _valid_schema(name: str) -> bool:
    return name.startswith("city_") and name.replace("_", "").isalnum()


def _list_city_schemas(conn) -> List[str]:
    rows = conn.execute(text(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name LIKE 'city\\_%' ORDER BY schema_name"
    )).fetchall()
    return [row[0] for row in rows]


def _existing_tables(conn, schema: str) -> List[str]:
    rows = conn.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = ANY(:tables)"
        ),
        {"schema": schema, "tables": list(WRITTEN_TEST_TABLES)},
    ).fetchall()
    return sorted(row[0] for row in rows)


def _row_count(conn, schema: str, table: str) -> int:
    return conn.execute(text(f'SELECT COUNT(*) FROM "{schema}".{table}')).scalar() or 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tabelas da avaliação escrita do Afirme Ler nos schemas city_* existentes."
    )
    parser.add_argument("--execute", action="store_true",
                        help="Grava no banco. Sem esta opção, só simula.")
    parser.add_argument("--rollback", action="store_true",
                        help="Apaga as tabelas em vez de criar.")
    parser.add_argument("--schema", action="append", dest="schemas",
                        help="Schema específico (pode repetir). Sem esta opção: todos os city_*.")
    args = parser.parse_args()

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        print("DATABASE_URL não encontrado. Configure app/.env.")
        return 1

    url = make_url(database_url)
    mode = "EXECUÇÃO" if args.execute else "SIMULAÇÃO (nada será gravado)"
    action = "ROLLBACK (apagar tabelas)" if args.rollback else "criar tabelas"
    print(f"Banco: {url.database} em {url.host}:{url.port}")
    print(f"Modo: {mode} | Ação: {action}")

    engine = create_engine(database_url)
    with engine.connect() as conn:
        schemas = args.schemas or _list_city_schemas(conn)
        invalid = [s for s in schemas if not _valid_schema(s)]
        if invalid:
            print(f"Schema inválido (deve começar com city_): {invalid[0]}")
            return 1
        known = set(_list_city_schemas(conn))
        missing = [s for s in schemas if s not in known]
        if missing:
            print(f"Schema não existe no banco: {missing[0]}")
            return 1

        plan = []
        for schema in schemas:
            existing = _existing_tables(conn, schema)
            if args.rollback:
                counts = {t: _row_count(conn, schema, t) for t in existing}
                plan.append((schema, existing, counts))
            else:
                to_create = [t for t in WRITTEN_TEST_TABLES if t not in existing]
                plan.append((schema, to_create, {}))
        conn.rollback()

    print(f"Schemas: {len(plan)}")
    for schema, tables, counts in plan:
        if args.rollback:
            detail = ", ".join(f"{t} ({counts[t]} linhas)" for t in tables) or "nada a apagar"
            print(f"  {schema}: apagaria {detail}")
        else:
            detail = ", ".join(tables) or "nada (tabelas já existem)"
            print(f"  {schema}: criaria {detail}")

    if not args.execute:
        print("Simulação concluída. Rode de novo com --execute para gravar.")
        return 0

    ok = failed = 0
    for schema, tables, _ in plan:
        if not tables:
            ok += 1
            continue
        ddl = _drop_ddl(schema) if args.rollback else get_afirme_ler_written_test_tables_ddl(schema)
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(ddl)
            print(f"OK: {schema}")
            ok += 1
        except Exception as exc:
            failed += 1
            print(f"FALHA: {schema}: {exc}")

    print(f"Resumo: ok={ok} falhas={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
