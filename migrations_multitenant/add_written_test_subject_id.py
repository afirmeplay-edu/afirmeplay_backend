# -*- coding: utf-8 -*-
"""
Adiciona subject_id em reading_written_test (schemas city_*), com backfill inteligente.

Backfill por avaliação:
  1. Se todas as questões vinculadas têm o mesmo subject_id → usa esse id.
  2. Se a prova não tem questões → Português resolvido pelo nome em public.subject.
  3. Se há subjects distintos → NÃO falha silenciosamente: lista no log e usa Português.

Resolve Português/Matemática em public.subject PELO NOME (não fixa IDs).
Se Português não for encontrado, o script falha com mensagem clara.

Padrão = SIMULAÇÃO (não grava).

Uso (na raiz do repositório):

  python migrations_multitenant/add_written_test_subject_id.py
  python migrations_multitenant/add_written_test_subject_id.py --execute
  python migrations_multitenant/add_written_test_subject_id.py --schema city_xxx --execute

Requer DATABASE_URL em app/.env (ou no ambiente).
"""
from __future__ import annotations

import argparse
import os
import sys
import unicodedata
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(os.path.join(ROOT, "app", ".env"))


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _norm(name: Optional[str]) -> str:
    if not name:
        return ""
    return " ".join(_strip_accents(str(name)).casefold().split())


def _subject_key(name: Optional[str]) -> Optional[str]:
    text_name = _norm(name)
    if not text_name:
        return None
    if "portugu" in text_name or text_name in {"lp", "lingua portuguesa"}:
        return "portugues"
    if "matem" in text_name:
        return "matematica"
    return None


def _valid_schema(name: str) -> bool:
    return name.startswith("city_") and name.replace("_", "").isalnum()


def _list_city_schemas(conn) -> List[str]:
    rows = conn.execute(text(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name LIKE 'city\\_%' ORDER BY schema_name"
    )).fetchall()
    return [row[0] for row in rows]


def _has_written_test(conn, schema: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = 'reading_written_test'"
        ),
        {"schema": schema},
    ).fetchone()
    return row is not None


def _has_column(conn, schema: str, column: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'reading_written_test' "
            "AND column_name = :column"
        ),
        {"schema": schema, "column": column},
    ).fetchone()
    return row is not None


def _resolve_portugues(conn) -> Tuple[str, str]:
    rows = conn.execute(text("SELECT id, name FROM public.subject")).fetchall()
    matches = [(str(row[0]), str(row[1] or "")) for row in rows if _subject_key(row[1]) == "portugues"]
    if not matches:
        raise RuntimeError(
            "Não foi possível encontrar a disciplina 'Português' em public.subject pelo nome. "
            "Cadastre-a (ou ajuste o nome para conter 'Português' / 'Portuguesa') antes de rodar."
        )
    matches.sort(key=lambda item: (len(item[1]), item[1], item[0]))
    return matches[0]


def _null_count(conn, schema: str) -> int:
    return int(conn.execute(
        text(f'SELECT COUNT(*) FROM "{schema}".reading_written_test WHERE subject_id IS NULL')
    ).scalar() or 0)


def _plan_backfill(conn, schema: str, portugues_id: str) -> List[Dict[str, object]]:
    """
    Monta o plano de backfill por avaliação.
    reason: questions_same | no_questions | mixed_subjects
    """
    rows = conn.execute(text(f"""
        SELECT
          wt.id AS test_id,
          wt.title AS title,
          array_agg(DISTINCT q.subject_id ORDER BY q.subject_id)
            FILTER (WHERE q.subject_id IS NOT NULL) AS subject_ids,
          COUNT(wtq.id) AS n_links
        FROM "{schema}".reading_written_test wt
        LEFT JOIN "{schema}".reading_written_test_question wtq
          ON wtq.written_test_id = wt.id
        LEFT JOIN public.question q ON q.id = wtq.question_id
        GROUP BY wt.id, wt.title
        ORDER BY wt.created_at, wt.id
    """)).fetchall()

    name_by_id: Dict[str, str] = {
        str(row[0]): str(row[1] or "")
        for row in conn.execute(text("SELECT id, name FROM public.subject")).fetchall()
    }

    plan: List[Dict[str, object]] = []
    for row in rows:
        test_id = str(row[0])
        title = str(row[1] or "")
        subject_ids = [str(sid) for sid in (row[2] or []) if sid]
        n_links = int(row[3] or 0)
        if len(subject_ids) == 1:
            chosen = subject_ids[0]
            reason = "questions_same"
        elif not subject_ids:
            chosen = portugues_id
            reason = "no_questions"
        else:
            chosen = portugues_id
            reason = "mixed_subjects"
        plan.append({
            "test_id": test_id,
            "title": title,
            "n_links": n_links,
            "subject_ids": subject_ids,
            "subject_names": [name_by_id.get(sid, "?") for sid in subject_ids],
            "chosen": chosen,
            "chosen_name": name_by_id.get(chosen, "?"),
            "reason": reason,
        })
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Adiciona subject_id em reading_written_test")
    parser.add_argument("--execute", action="store_true", help="Grava no banco (padrão: simulação)")
    parser.add_argument("--schema", action="append", default=[], help="Schema city_* (repetível)")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL não definido.", file=sys.stderr)
        return 1

    url = make_url(database_url)
    print(f"Banco: {url.host}:{url.port}/{url.database}  modo={'EXECUTE' if args.execute else 'SIMULAÇÃO'}")

    engine = create_engine(database_url)
    # Simulação: conexão de leitura. Execute: uma transação (begin) por schema.
    connect_ctx = engine.begin if args.execute else engine.connect
    with connect_ctx() as first_conn:
        portugues_id, portugues_name = _resolve_portugues(first_conn)
        print(f"Português resolvido: id={portugues_id} name={portugues_name!r}")
        schemas = args.schema or _list_city_schemas(first_conn)
        schemas = [s for s in schemas if _valid_schema(s)]

    schemas_with = 0
    total_tests = 0
    mixed_total = 0

    for schema in schemas:
        with connect_ctx() as conn:
            if not _has_written_test(conn, schema):
                continue
            schemas_with += 1
            has_col = _has_column(conn, schema, "subject_id")
            plan = _plan_backfill(conn, schema, portugues_id)
            total_tests += len(plan)
            mixed = [item for item in plan if item["reason"] == "mixed_subjects"]
            mixed_total += len(mixed)
            same = sum(1 for item in plan if item["reason"] == "questions_same")
            empty = sum(1 for item in plan if item["reason"] == "no_questions")
            print(
                f"  {schema}: column={'sim' if has_col else 'não'} "
                f"provas={len(plan)} same={same} empty={empty} mixed={len(mixed)}"
            )
            for item in plan:
                if item["reason"] == "mixed_subjects":
                    print(
                        f"    ! MIXED test={item['test_id']} title={item['title']!r} "
                        f"subjects={list(zip(item['subject_ids'], item['subject_names']))} "
                        f"→ fallback Português ({portugues_id})"
                    )
                elif item["reason"] == "questions_same":
                    print(
                        f"    = same test={item['test_id']} title={item['title']!r} "
                        f"→ {item['chosen']} ({item['chosen_name']})"
                    )
                else:
                    print(
                        f"    · empty test={item['test_id']} title={item['title']!r} "
                        f"→ Português ({portugues_id})"
                    )

            if not args.execute:
                continue

            if not has_col:
                conn.execute(text(
                    f'ALTER TABLE "{schema}".reading_written_test '
                    "ADD COLUMN IF NOT EXISTS subject_id VARCHAR"
                ))
            for item in plan:
                conn.execute(
                    text(
                        f'UPDATE "{schema}".reading_written_test '
                        "SET subject_id = :sid WHERE id = :tid"
                    ),
                    {"sid": item["chosen"], "tid": item["test_id"]},
                )
            # Qualquer linha ainda NULL (corrida / prova criada no meio) → Português.
            conn.execute(
                text(
                    f'UPDATE "{schema}".reading_written_test '
                    "SET subject_id = :sid WHERE subject_id IS NULL"
                ),
                {"sid": portugues_id},
            )
            remaining = _null_count(conn, schema)
            if remaining:
                raise RuntimeError(
                    f"{schema}: ainda há {remaining} avaliações sem subject_id após o backfill."
                )
            conn.execute(text(
                f'ALTER TABLE "{schema}".reading_written_test '
                "ALTER COLUMN subject_id SET NOT NULL"
            ))
            conn.execute(text(
                f'CREATE INDEX IF NOT EXISTS ix_reading_written_test_subject '
                f'ON "{schema}".reading_written_test(subject_id)'
            ))

    print(
        f"Schemas com tabela: {schemas_with}; provas: {total_tests}; "
        f"mixed (fallback Português): {mixed_total}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
