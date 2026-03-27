"""
Cria tabelas mobile (mobile_device, mobile_sync_submission, mobile_sync_bundle_generation)
em todos os schemas city_* existentes no PostgreSQL.

Idempotente: CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS.

Uso (a partir da raiz do repositório):
    python scripts/create_mobile_tables.py

Requer DATABASE_URL (ou uso do app/.env via create_app).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402
from app.services.mobile.ddl import get_mobile_tables_ddl  # noqa: E402


def list_city_schemas():
    rows = db.session.execute(
        text(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name ~ '^city_'
            ORDER BY schema_name
            """
        )
    ).fetchall()
    return [r[0] for r in rows]


def main():
    app = create_app()
    with app.app_context():
        schemas = list_city_schemas()
        if not schemas:
            print("Nenhum schema city_* encontrado.")
            return 0
        raw = db.engine.raw_connection()
        try:
            raw.set_isolation_level(0)
            cur = raw.cursor()
            for schema in schemas:
                ddl = get_mobile_tables_ddl(schema)
                cur.execute(ddl)
                print(f"OK: tabelas mobile em {schema}")
        finally:
            raw.close()
        print(f"Concluído. Schemas processados: {len(schemas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
