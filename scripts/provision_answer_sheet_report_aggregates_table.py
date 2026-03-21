#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cria a tabela answer_sheet_report_aggregates em todos os schemas city_xxx que possuem answer_sheet_gabaritos.

Não usa Alembic: a tabela fica no schema de cada município. Novos municípios recebem o DDL via
app.services.city_schema_service.provision_city_schema.

Uso (na raiz do projeto, com venv ativado):
  python scripts/provision_answer_sheet_report_aggregates_table.py

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


def ddl_for_schema(schema: str) -> list:
    q = f'"{schema}"'
    return [
        f"""
    CREATE TABLE IF NOT EXISTS {q}.answer_sheet_report_aggregates (
        id VARCHAR PRIMARY KEY,
        gabarito_id VARCHAR NOT NULL REFERENCES {q}.answer_sheet_gabaritos(id) ON DELETE CASCADE,
        scope_type VARCHAR(32) NOT NULL,
        scope_id VARCHAR,
        payload JSON NOT NULL DEFAULT '{{}}'::json,
        student_count INTEGER NOT NULL DEFAULT 0,
        ai_analysis JSON DEFAULT '{{}}'::json,
        ai_analysis_generated_at TIMESTAMP,
        ai_analysis_is_dirty BOOLEAN NOT NULL DEFAULT false,
        generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        is_dirty BOOLEAN NOT NULL DEFAULT false,
        CONSTRAINT uq_answer_sheet_report_aggregate_scope UNIQUE(gabarito_id, scope_type, scope_id)
    )
    """,
        f"COMMENT ON TABLE {q}.answer_sheet_report_aggregates IS 'Cache de relatórios agregados para cartão-resposta'",
        f"CREATE INDEX IF NOT EXISTS idx_as_report_agg_gabarito ON {q}.answer_sheet_report_aggregates(gabarito_id)",
        f"CREATE INDEX IF NOT EXISTS idx_as_report_agg_scope ON {q}.answer_sheet_report_aggregates(scope_type, scope_id)",
    ]


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERRO: Defina DATABASE_URL (em app/.env ou variável de ambiente).")
        sys.exit(1)

    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    ok = []
    errors = []

    with engine.connect() as conn:
        r = conn.execute(
            text("""
            SELECT DISTINCT table_schema
            FROM information_schema.tables
            WHERE table_schema LIKE 'city_%' AND table_name = 'answer_sheet_gabaritos'
            ORDER BY table_schema
            """)
        )
        schemas = [row[0] for row in r]

        if not schemas:
            print("Nenhum schema city_xxx com tabela answer_sheet_gabaritos encontrado.")
            return

        print(f"Schemas com answer_sheet_gabaritos: {len(schemas)}")

        for schema in schemas:
            if not (
                schema
                and isinstance(schema, str)
                and schema.startswith("city_")
                and all(c.isalnum() or c == "_" for c in schema)
            ):
                print(f"  [{schema}] Ignorado (nome inválido).")
                continue
            try:
                for stmt in ddl_for_schema(schema):
                    conn.execute(text(stmt))
                ok.append(schema)
                print(f"  [{schema}] answer_sheet_report_aggregates OK.")
            except Exception as e:
                errors.append((schema, str(e)))
                print(f"  [{schema}] ERRO: {e}")

    if errors:
        print(f"\nErros em {len(errors)} schema(s):")
        for s, err in errors:
            print(f"  {s}: {err}")
    print(f"\nConcluído. Schemas processados com sucesso: {len(ok)}.")


if __name__ == "__main__":
    main()
