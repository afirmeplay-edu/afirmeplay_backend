#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adiciona colunas last_generation_classes_count e last_generation_students_count
na tabela answer_sheet_gabaritos em todos os schemas city_xxx que possuem a tabela.

Uso (na raiz do projeto, com venv ativado):
  python scripts/add_last_generation_columns_answer_sheet_gabaritos.py

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


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERRO: Defina DATABASE_URL (em app/.env ou variável de ambiente).")
        sys.exit(1)

    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    updated = []
    errors = []

    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT DISTINCT table_schema
            FROM information_schema.tables
            WHERE table_schema LIKE 'city_%' AND table_name = 'answer_sheet_gabaritos'
            ORDER BY table_schema
        """))
        schemas = [row[0] for row in r]

        if not schemas:
            print("Nenhum schema city_xxx com tabela answer_sheet_gabaritos encontrado.")
            return

        print(f"Schemas com answer_sheet_gabaritos: {len(schemas)}")

        for schema in schemas:
            if not (schema and isinstance(schema, str) and all(c.isalnum() or c in "_" for c in schema)):
                print(f"  [{schema}] Ignorado (nome inválido).")
                continue
            quoted_schema = f'"{schema}"'

            check = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = 'answer_sheet_gabaritos'
                AND column_name IN ('last_generation_classes_count', 'last_generation_students_count')
            """), {"schema": schema})
            existing = {row[0] for row in check}

            try:
                if "last_generation_classes_count" not in existing:
                    conn.execute(text(
                        f'ALTER TABLE {quoted_schema}.answer_sheet_gabaritos '
                        'ADD COLUMN last_generation_classes_count INTEGER NULL'
                    ))
                    print(f"  [{schema}] last_generation_classes_count adicionada.")
                    updated.append(schema)
                else:
                    print(f"  [{schema}] last_generation_classes_count já existe.")

                if "last_generation_students_count" not in existing:
                    conn.execute(text(
                        f'ALTER TABLE {quoted_schema}.answer_sheet_gabaritos '
                        'ADD COLUMN last_generation_students_count INTEGER NULL'
                    ))
                    print(f"  [{schema}] last_generation_students_count adicionada.")
                    if schema not in updated:
                        updated.append(schema)
                else:
                    print(f"  [{schema}] last_generation_students_count já existe.")
            except Exception as e:
                errors.append((schema, str(e)))
                print(f"  [{schema}] ERRO: {e}")

    if errors:
        print(f"\nErros em {len(errors)} schema(s):")
        for s, err in errors:
            print(f"  {s}: {err}")
    print(f"\nConcluído. Schemas alterados: {len(updated)}.")


if __name__ == "__main__":
    main()
