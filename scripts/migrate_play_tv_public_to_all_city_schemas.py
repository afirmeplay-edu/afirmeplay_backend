#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migra Play TV do legado public.play_tv_videos para o schema de cada município (city_*).

Para cada schema city_*:
  1. Aplica DDL Play TV (idempotente) se não usar --skip-provision.
  2. Copia vídeos faltantes de public para {schema}.play_tv_videos conforme IDs
     usados em play_tv_video_schools, play_tv_video_classes e play_tv_video_resources.
  3. Se as FKs de video_id ainda apontarem para public.play_tv_videos, remove e recria
     apontando para {schema}.play_tv_videos.

Não usa Alembic. Faça backup do banco antes de rodar em produção.

Uso (raiz do projeto, venv, DATABASE_URL em app/.env):
  python scripts/migrate_play_tv_public_to_all_city_schemas.py
  python scripts/migrate_play_tv_public_to_all_city_schemas.py --dry-run
  python scripts/migrate_play_tv_public_to_all_city_schemas.py --schema city_xxxxxxxx
  python scripts/migrate_play_tv_public_to_all_city_schemas.py --skip-provision

Depois, valide com:
  python scripts/check_play_tv_fk_city_schemas.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_env = _project_root / "app" / ".env"
if _env.exists():
    from dotenv import load_dotenv

    load_dotenv(_env)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migra Play TV public → todos os schemas city_*"
    )
    parser.add_argument(
        "--schema",
        help="Processar apenas este schema (ex.: city_9a2f95ed_9f70_4863_a5f1_1b6c6c262b0d)",
    )
    parser.add_argument(
        "--skip-provision",
        action="store_true",
        help="Não executar DDL Play TV (apenas backfill + realinhamento de FK)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Listar schemas que seriam processados, sem alterar o banco",
    )
    args = parser.parse_args()

    from sqlalchemy import text

    from app import create_app, db
    from app.services.city_schema_service import (
        migrate_play_tv_from_public_to_city_schema,
        provision_play_tv_for_city_schema,
    )

    app = create_app()
    with app.app_context():
        if args.schema:
            schemas = [args.schema]
        else:
            rows = db.session.execute(
                text(
                    "SELECT nspname FROM pg_namespace "
                    "WHERE nspname LIKE 'city\\_%' ESCAPE '\\' ORDER BY nspname"
                )
            )
            schemas = [r[0] for r in rows]

        if not schemas:
            print("Nenhum schema city_* encontrado.")
            return

        print("=" * 80)
        print("Play TV — migração public → city_* (todos os tenants listados)")
        print("=" * 80)

        for schema in schemas:
            if args.dry_run:
                print(
                    f"[dry-run] schema={schema} "
                    f"provision={not args.skip_provision} migrate=sim"
                )
                continue
            if not args.skip_provision:
                print(f"DDL Play TV → {schema} …")
                provision_play_tv_for_city_schema(schema)
            print(f"Migração dados/FK → {schema} …")
            out = migrate_play_tv_from_public_to_city_schema(schema)
            print(f"  {out}")

        if args.dry_run:
            print(f"\nTotal de schemas (dry-run): {len(schemas)}")
        else:
            print("\nConcluído. Rode: python scripts/check_play_tv_fk_city_schemas.py")


if __name__ == "__main__":
    main()
