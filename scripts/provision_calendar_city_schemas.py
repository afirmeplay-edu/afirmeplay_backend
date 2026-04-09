#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garante as estruturas de Calendar em cada schema city_*.

Uso:
  python scripts/provision_calendar_city_schemas.py
  python scripts/provision_calendar_city_schemas.py --schema city_xxxxx
  python scripts/provision_calendar_city_schemas.py --dry-run
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
    parser = argparse.ArgumentParser(description="Provisiona estruturas de Calendar nos schemas city_*")
    parser.add_argument("--schema", help="Aplicar só neste schema (ex.: city_...)")
    parser.add_argument("--dry-run", action="store_true", help="Somente listar schemas")
    args = parser.parse_args()

    from sqlalchemy import text
    from app import create_app, db
    from app.services.city_schema_service import provision_calendar_for_city_schema

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
                print(f"[dry-run] schema={schema}")
                continue
            print(f"Calendar DDL -> {schema} ...")
            provision_calendar_for_city_schema(schema)


if __name__ == "__main__":
    main()
