"""
Verifica em quais schemas a tabela competitions tem as colunas edition_number e edition_series.
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
        conn = db.session.connection()

        # 1) Schemas que têm tabela 'competitions'
        r = conn.execute(text("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name = 'competitions'
            ORDER BY table_schema
        """))
        schemas_with_competitions = [row[0] for row in r.fetchall()]
        print("Schemas com tabela 'competitions':", schemas_with_competitions or "(nenhum)")

        # 2) Para cada schema, verificar se tem as colunas edition_number e edition_series
        for schema in schemas_with_competitions:
            r = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = 'competitions'
                AND column_name IN ('edition_number', 'edition_series')
                ORDER BY column_name
            """), {"schema": schema})
            cols = [row[0] for row in r.fetchall()]
            has_both = "edition_number" in cols and "edition_series" in cols
            print(f"  {schema}.competitions: edition_number={('edition_number' in cols)}, edition_series={('edition_series' in cols)} -> {'OK (tem as duas)' if has_both else 'FALTA coluna(s)'}")

        # 3) Resumo: só public tem?
        public_ok = False
        city_missing = []
        for schema in schemas_with_competitions:
            r = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = 'competitions'
                AND column_name IN ('edition_number', 'edition_series')
            """), {"schema": schema})
            cols = [row[0] for row in r.fetchall()]
            has_both = "edition_number" in cols and "edition_series" in cols
            if schema == "public":
                public_ok = has_both
            elif schema.startswith("city_"):
                if not has_both:
                    city_missing.append(schema)

        print("")
        print("Resumo:")
        print(f"  public.competitions tem as duas colunas: {public_ok}")
        print(f"  Schemas city_xxx sem as colunas: {city_missing if city_missing else 'nenhum (ou não há city_xxx com competitions)'}")


if __name__ == "__main__":
    main()
