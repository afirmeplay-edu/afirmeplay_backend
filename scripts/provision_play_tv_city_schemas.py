#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garante as tabelas Play TV (play_tv_videos, play_tv_video_resources,
play_tv_video_schools, play_tv_video_classes) em cada schema city_*.

- Novos municípios: o DDL já roda em app.services.city_schema_service.provision_city_schema
  ao criar a cidade (POST /city).

- Municípios existentes: execute este script uma vez (ou sempre que o DDL Play TV evoluir).

Opcional: --migrate-from-public
  Copia vídeos de public.play_tv_videos para o tenant e realinha FKs das tabelas de junção,
  quando ainda apontavam para public (legado).

Uso (raiz do projeto, venv ativado):
  python scripts/provision_play_tv_city_schemas.py
  python scripts/provision_play_tv_city_schemas.py --schema city_xxxxxxxx
  python scripts/provision_play_tv_city_schemas.py --migrate-from-public
  python scripts/provision_play_tv_city_schemas.py --dry-run

Requer: DATABASE_URL em app/.env
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
    parser = argparse.ArgumentParser(description="Provisiona tabelas Play TV nos schemas city_*")
    parser.add_argument(
        "--schema",
        help="Aplicar só neste schema (ex.: city_9a2f95ed_9f70_4863_a5f1_1b6c6c262b0d)",
    )
    parser.add_argument(
        "--migrate-from-public",
        action="store_true",
        help="Após o DDL, migrar dados/FKs legados de public.play_tv_videos (por tenant)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Somente listar schemas")
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

        for schema in schemas:
            if args.dry_run:
                print(f"[dry-run] schema={schema} migrate={args.migrate_from_public}")
                continue
            print(f"Play TV DDL → {schema} …")
            provision_play_tv_for_city_schema(schema)
            if args.migrate_from_public:
                print(f"  migrando FK/dados public → {schema} …")
                out = migrate_play_tv_from_public_to_city_schema(schema)
                print(f"  resultado: {out}")


if __name__ == "__main__":
    main()
