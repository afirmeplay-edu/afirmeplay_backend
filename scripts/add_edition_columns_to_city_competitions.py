"""
Adiciona as colunas edition_number e edition_series na tabela competitions
dos schemas city_xxx que ainda não as possuem.

Migrations só alteram public; este script corrige os schemas tenant (city_xxx).
Execute: python scripts/add_edition_columns_to_city_competitions.py
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
except ImportError:
    pass

from app import create_app, db
from sqlalchemy import text


def main():
    app = create_app()
    with app.app_context():
        # Usar engine diretamente para evitar conexão fechada após commit
        with db.engine.connect() as conn:
            r = conn.execute(text("""
                SELECT table_schema
                FROM information_schema.tables
                WHERE table_name = 'competitions'
                  AND table_schema LIKE 'city_%'
                ORDER BY table_schema
            """))
            city_schemas = [row[0] for row in r.fetchall()]

        if not city_schemas:
            print("Nenhum schema city_xxx com tabela competitions encontrado.")
            return

        updated = []
        for schema in city_schemas:
            with db.engine.connect() as conn:
                r = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = :schema AND table_name = 'competitions'
                      AND column_name IN ('edition_number', 'edition_series')
                """), {"schema": schema})
                cols = [row[0] for row in r.fetchall()]

                safe_schema = schema.replace('"', '""')
                qual = f'"{safe_schema}".competitions'

                changed = False
                if "edition_number" not in cols:
                    conn.execute(text(f'ALTER TABLE {qual} ADD COLUMN edition_number INTEGER NULL'))
                    print(f"  {schema}.competitions: coluna edition_number adicionada.")
                    changed = True
                if "edition_series" not in cols:
                    conn.execute(text(f'ALTER TABLE {qual} ADD COLUMN edition_series VARCHAR NULL'))
                    print(f"  {schema}.competitions: coluna edition_series adicionada.")
                    changed = True
                if changed:
                    conn.commit()
                    updated.append(schema)

        if updated:
            print(f"\nConcluído: colunas adicionadas em {len(updated)} schema(s) city_xxx.")
        else:
            print("Nenhum schema precisou de alteração (todos já tinham as colunas).")


if __name__ == "__main__":
    main()
