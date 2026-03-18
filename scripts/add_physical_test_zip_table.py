#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cria a tabela physical_test_zip em todos os schemas city_xxx que possuem a tabela test.

A tabela guarda minio_url, minio_object_name, minio_bucket, zip_generated_at por prova (test_id),
para o domínio de provas físicas (download all), sem usar answer_sheet_gabaritos.

Uso (na raiz do projeto, com venv ativado):
  python scripts/add_physical_test_zip_table.py

Requer: DATABASE_URL em app/.env (ou variável de ambiente).
"""
from pathlib import Path
import os
import sys

_project_root = Path(__file__).resolve().parent.parent
_env_path = _project_root / "app" / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("ERRO: Instale sqlalchemy (pip install sqlalchemy)")
    sys.exit(1)


# SQL idêntico ao do city_schema_service (CREATE TABLE para novo city)
def create_table_sql(schema: str) -> str:
    quoted = f'"{schema}"'
    return f"""
    CREATE TABLE IF NOT EXISTS {quoted}.physical_test_zip (
        test_id VARCHAR PRIMARY KEY REFERENCES {quoted}.test(id),
        minio_url VARCHAR(500),
        minio_object_name VARCHAR(200),
        minio_bucket VARCHAR(100),
        zip_generated_at TIMESTAMP
    )
    """


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERRO: Defina DATABASE_URL (em app/.env ou variável de ambiente).")
        sys.exit(1)

    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    created = []
    errors = []

    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT DISTINCT table_schema
            FROM information_schema.tables
            WHERE table_schema LIKE 'city_%%' AND table_name = 'test'
            ORDER BY table_schema
        """))
        schemas = [row[0] for row in r]

        if not schemas:
            print("Nenhum schema city_xxx com tabela test encontrado.")
            return

        print(f"Schemas city_xxx com tabela test: {len(schemas)}")

        for schema in schemas:
            if not (schema and isinstance(schema, str) and schema.startswith("city_") and all(c.isalnum() or c == "_" for c in schema)):
                print(f"  [{schema}] Ignorado (nome inválido).")
                continue

            try:
                sql = create_table_sql(schema)
                conn.execute(text(sql))
                created.append(schema)
                print(f"  [{schema}] Tabela physical_test_zip criada ou já existia.")
            except Exception as e:
                errors.append((schema, str(e)))
                print(f"  [{schema}] ERRO: {e}")

    if errors:
        print(f"\nErros em {len(errors)} schema(s):")
        for s, err in errors:
            print(f"  {s}: {err}")
    print(f"\nConcluído. Schemas processados: {len(created)}.")


if __name__ == "__main__":
    main()
