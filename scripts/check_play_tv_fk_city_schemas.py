#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico Play TV em todos os schemas city_*:

- Junções `play_tv_video_schools` / `play_tv_video_classes` com `video_id` inexistente
  em `city_xxx.play_tv_videos` (causa típica de ForeignKeyViolation no POST).
- Indica se o mesmo `video_id` existe em `public.play_tv_videos` (cenário legado:
  vídeo só no public, escolas no tenant).

Não altera dados — somente leitura.

Uso (raiz do projeto, venv, app/.env com DATABASE_URL):
  python scripts/check_play_tv_fk_city_schemas.py
  python scripts/check_play_tv_fk_city_schemas.py --schema city_xxxxxxxx
  python scripts/check_play_tv_fk_city_schemas.py --verbose

Após revisar, para corrigir em todos os tenants:
  python scripts/migrate_play_tv_public_to_all_city_schemas.py

Um tenant só:
  python scripts/provision_play_tv_city_schemas.py --schema city_xxx --migrate-from-public
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_env = _project_root / "app" / ".env"
if _env.exists():
    from dotenv import load_dotenv

    load_dotenv(_env)


def _table_exists(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cursor.fetchone() is not None


def _public_play_tv_videos_exists(cursor) -> bool:
    return _table_exists(cursor, "public", "play_tv_videos")


def _count_orphan_schools(cursor, schema: str) -> int:
    cursor.execute(
        f"""
        SELECT COUNT(*)::bigint
        FROM "{schema}".play_tv_video_schools vs
        LEFT JOIN "{schema}".play_tv_videos v ON v.id = vs.video_id
        WHERE v.id IS NULL
        """
    )
    return int(cursor.fetchone()[0])


def _count_orphan_classes(cursor, schema: str) -> int:
    cursor.execute(
        f"""
        SELECT COUNT(*)::bigint
        FROM "{schema}".play_tv_video_classes vc
        LEFT JOIN "{schema}".play_tv_videos v ON v.id = vc.video_id
        WHERE v.id IS NULL
        """
    )
    return int(cursor.fetchone()[0])


def _orphan_schools_only_in_public(cursor, schema: str) -> int:
    """Junções órfãs no tenant cujo video_id existe em public.play_tv_videos."""
    cursor.execute(
        f"""
        SELECT COUNT(*)::bigint
        FROM "{schema}".play_tv_video_schools vs
        LEFT JOIN "{schema}".play_tv_videos v ON v.id = vs.video_id
        INNER JOIN public.play_tv_videos pv ON pv.id = vs.video_id
        WHERE v.id IS NULL
        """
    )
    return int(cursor.fetchone()[0])


def _orphan_classes_only_in_public(cursor, schema: str) -> int:
    cursor.execute(
        f"""
        SELECT COUNT(*)::bigint
        FROM "{schema}".play_tv_video_classes vc
        LEFT JOIN "{schema}".play_tv_videos v ON v.id = vc.video_id
        INNER JOIN public.play_tv_videos pv ON pv.id = vc.video_id
        WHERE v.id IS NULL
        """
    )
    return int(cursor.fetchone()[0])


def _sample_orphan_video_ids_schools(cursor, schema: str, limit: int) -> List[str]:
    cursor.execute(
        f"""
        SELECT DISTINCT vs.video_id
        FROM "{schema}".play_tv_video_schools vs
        LEFT JOIN "{schema}".play_tv_videos v ON v.id = vs.video_id
        WHERE v.id IS NULL
        LIMIT %s
        """,
        (limit,),
    )
    return [str(r[0]) for r in cursor.fetchall() if r[0]]


def _fk_target_schema_for_table(cursor, schema: str, table: str) -> Optional[str]:
    """Schema da tabela play_tv_videos referenciada por FK a partir de `table`."""
    cursor.execute(
        """
        SELECT rn.nspname::text
        FROM pg_constraint c
        JOIN pg_class rel ON rel.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        JOIN pg_class ref ON ref.oid = c.confrelid
        JOIN pg_namespace rn ON rn.oid = ref.relnamespace
        WHERE c.contype = 'f'
          AND n.nspname = %s
          AND rel.relname = %s
          AND ref.relname = 'play_tv_videos'
        LIMIT 1
        """,
        (schema, table),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def audit_schema(cursor, schema: str, verbose: bool, has_public_videos: bool) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "schema": schema,
        "has_play_tv_videos": False,
        "has_play_tv_video_schools": False,
        "has_play_tv_video_classes": False,
        "orphan_schools": 0,
        "orphan_classes": 0,
        "orphan_schools_in_public": 0,
        "orphan_classes_in_public": 0,
        "fk_schools_refs_schema": None,
        "fk_classes_refs_schema": None,
        "sample_orphan_video_ids": [],
        "status": "skip",
    }

    out["has_play_tv_videos"] = _table_exists(cursor, schema, "play_tv_videos")
    out["has_play_tv_video_schools"] = _table_exists(cursor, schema, "play_tv_video_schools")
    out["has_play_tv_video_classes"] = _table_exists(cursor, schema, "play_tv_video_classes")

    if not out["has_play_tv_videos"]:
        out["status"] = "no_local_videos_table"
        return out

    if out["has_play_tv_video_schools"]:
        out["fk_schools_refs_schema"] = _fk_target_schema_for_table(
            cursor, schema, "play_tv_video_schools"
        )
    if out["has_play_tv_video_classes"]:
        out["fk_classes_refs_schema"] = _fk_target_schema_for_table(
            cursor, schema, "play_tv_video_classes"
        )

    if out["has_play_tv_video_schools"]:
        out["orphan_schools"] = _count_orphan_schools(cursor, schema)
        if has_public_videos:
            out["orphan_schools_in_public"] = _orphan_schools_only_in_public(cursor, schema)
        if verbose and out["orphan_schools"] > 0:
            out["sample_orphan_video_ids"] = _sample_orphan_video_ids_schools(
                cursor, schema, limit=8
            )

    if out["has_play_tv_video_classes"]:
        out["orphan_classes"] = _count_orphan_classes(cursor, schema)
        if has_public_videos:
            out["orphan_classes_in_public"] = _orphan_classes_only_in_public(cursor, schema)

    if out["orphan_schools"] > 0 or out["orphan_classes"] > 0:
        out["status"] = "problem"
    elif not out["has_play_tv_video_schools"] and not out["has_play_tv_video_classes"]:
        out["status"] = "videos_only"
    else:
        out["status"] = "ok"

    return out


def print_report(rows: List[Dict[str, Any]], verbose: bool) -> None:
    problems = [r for r in rows if r["status"] == "problem"]
    print("=" * 80)
    print("Play TV — diagnóstico FK / vídeos por schema city_*")
    print("=" * 80)

    for r in rows:
        if r.get("status") == "error":
            print(f"[{r['schema']}] ERRO ao inspecionar: {r.get('error', '')}")
            continue
        line = (
            f"[{r['schema']}] status={r['status']} "
            f"orphan_schools={r['orphan_schools']} orphan_classes={r['orphan_classes']}"
        )
        if r.get("orphan_schools_in_public") or r.get("orphan_classes_in_public"):
            line += (
                f" | órfãos com vídeo só em public: "
                f"schools={r['orphan_schools_in_public']} classes={r['orphan_classes_in_public']}"
            )
        print(line)
        if verbose:
            if r.get("fk_schools_refs_schema"):
                print(f"         FK play_tv_video_schools.video_id -> schema {r['fk_schools_refs_schema']}")
            if r.get("fk_classes_refs_schema"):
                print(f"         FK play_tv_video_classes.video_id -> schema {r['fk_classes_refs_schema']}")
            if r.get("sample_orphan_video_ids"):
                print(f"         exemplos video_id órfão: {r['sample_orphan_video_ids']}")

    print("-" * 80)
    print(f"Schemas com problema (junção sem vídeo local): {len(problems)}")
    if problems:
        for r in problems:
            print(f"  - {r['schema']}")
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verifica Play TV (FK vídeo x junções) em todos os city_*"
    )
    parser.add_argument("--schema", help="Inspecionar só este schema (ex.: city_...)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mais detalhes por schema")
    args = parser.parse_args()

    from app import create_app, db

    app = create_app()
    with app.app_context():
        raw = db.engine.raw_connection()
        try:
            cursor = raw.cursor()
            if args.schema:
                schemas = [args.schema]
            else:
                cursor.execute(
                    """
                    SELECT nspname FROM pg_namespace
                    WHERE nspname LIKE 'city\\_%' ESCAPE '\\'
                    ORDER BY nspname
                    """
                )
                schemas = [r[0] for r in cursor.fetchall()]

            has_public = _public_play_tv_videos_exists(cursor)
            if not has_public:
                print("(Aviso) Tabela public.play_tv_videos não existe; colunas 'órfão em public' serão 0.\n")

            results: List[Dict[str, Any]] = []
            for schema in schemas:
                try:
                    row = audit_schema(cursor, schema, args.verbose, has_public)
                    results.append(row)
                except Exception as ex:
                    results.append(
                        {
                            "schema": schema,
                            "status": "error",
                            "error": str(ex),
                            "orphan_schools": 0,
                            "orphan_classes": 0,
                            "orphan_schools_in_public": 0,
                            "orphan_classes_in_public": 0,
                        }
                    )

            print_report(results, args.verbose)

            errors = [r for r in results if r.get("status") == "error"]
            problems = [r for r in results if r.get("status") == "problem"]
            if errors:
                sys.exit(2)
            if problems:
                sys.exit(1)
            sys.exit(0)
        finally:
            raw.close()


if __name__ == "__main__":
    main()
