#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adiciona a coluna proficiency_by_subject na tabela answer_sheet_results
em todos os schemas city_xxx do banco de dados.

A tabela answer_sheet_results fica em cada schema de cidade (não em public).
Este script é idempotente: verifica se a coluna já existe antes de adicionar.

Uso (na raiz do projeto, com venv ativado):
  python scripts/add_proficiency_by_subject_to_answer_sheet_results.py

Opções:
  --dry-run   Apenas lista os schemas e o que seria feito, sem alterar o banco.

Requer: DATABASE_URL em app/.env (ou variável de ambiente).
"""
from pathlib import Path
import os
import sys
import argparse

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


def _safe_schema_name(schema: str) -> bool:
    """Retorna True se o nome do schema é seguro (city_ + alfanumérico/underscore)."""
    return (
        schema
        and isinstance(schema, str)
        and schema.startswith("city_")
        and all(c.isalnum() or c == "_" for c in schema)
    )


def main():
    parser = argparse.ArgumentParser(description="Adiciona coluna proficiency_by_subject em answer_sheet_results (todos os schemas city_xxx)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas listar schemas e ações, sem alterar o banco")
    args = parser.parse_args()
    dry_run = args.dry_run

    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERRO: Defina DATABASE_URL (em app/.env ou variável de ambiente).")
        sys.exit(1)

    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    added = []
    skipped_no_table = []
    skipped_has_column = []
    added_count = 0
    errors = []

    with engine.connect() as conn:
        # Schemas city_* que existem no banco
        r = conn.execute(text("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name LIKE 'city_%'
            ORDER BY schema_name
        """))
        all_schemas = [row[0] for row in r]

        if not all_schemas:
            print("Nenhum schema city_xxx encontrado no banco.")
            return

        print(f"Encontrados {len(all_schemas)} schemas city_xxx.")
        if dry_run:
            print("[DRY RUN] Nenhuma alteração será feita.\n")

        for schema in all_schemas:
            if not _safe_schema_name(schema):
                continue

            # Verificar se a tabela answer_sheet_results existe neste schema
            r = conn.execute(text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = :schema AND table_name = 'answer_sheet_results'
            """), {"schema": schema})
            if not r.fetchone():
                skipped_no_table.append(schema)
                if dry_run:
                    print(f"  [DRY RUN] {schema}: tabela answer_sheet_results não existe (ignorado)")
                continue

            # Verificar se a coluna proficiency_by_subject já existe
            r = conn.execute(text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = 'answer_sheet_results'
                  AND column_name = 'proficiency_by_subject'
            """), {"schema": schema})
            if r.fetchone():
                skipped_has_column.append(schema)
                if dry_run:
                    print(f"  [DRY RUN] {schema}: coluna já existe (ignorado)")
                continue

            if dry_run:
                print(f"  [DRY RUN] {schema}: adicionaria coluna proficiency_by_subject")
                added.append(schema)
                added_count += 1
                continue

            # Adicionar coluna (schema qualificado entre aspas para preservar minúsculas)
            try:
                # PostgreSQL: identifier entre aspas duplas (schema já validado por _safe_schema_name)
                sql = text(f'ALTER TABLE "{schema}".answer_sheet_results ADD COLUMN IF NOT EXISTS proficiency_by_subject JSONB NULL')
                conn.execute(sql)
                added.append(schema)
                added_count += 1
                print(f"  OK {schema}: coluna proficiency_by_subject adicionada.")
            except Exception as e:
                errors.append((schema, str(e)))
                print(f"  ERRO {schema}: {e}")

    # Resumo
    print()
    print("Resumo:")
    print(f"  - Coluna adicionada: {added_count} schema(s)")
    if skipped_has_column:
        print(f"  - Já tinham a coluna: {len(skipped_has_column)} schema(s)")
    if skipped_no_table:
        print(f"  - Sem tabela answer_sheet_results: {len(skipped_no_table)} schema(s)")
    if errors:
        print(f"  - Erros: {len(errors)}")
        for schema, err in errors:
            print(f"      {schema}: {err}")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
