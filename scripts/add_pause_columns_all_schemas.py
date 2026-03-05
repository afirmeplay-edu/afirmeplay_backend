#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adiciona colunas de pausa do timer (paused_at, total_paused_seconds) em test_sessions
em TODOS os schemas que possuem a tabela test_sessions (public + city_xxx no multi-tenant).

Uso (na raiz do projeto, com venv ativado):
  python scripts/add_pause_columns_all_schemas.py

Requer: DATABASE_URL em app/.env (ou variável de ambiente).

Depois de rodar: descomente as colunas paused_at e total_paused_seconds em
app/models/testSession.py para o recurso de pausa do timer funcionar.
"""
from pathlib import Path
import os
import sys

# Carregar .env do app
_project_root = Path(__file__).resolve().parent.parent
_env_path = _project_root / "app" / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("Instale: pip install sqlalchemy")
    sys.exit(1)


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERRO: Defina DATABASE_URL (em app/.env ou ambiente).")
        sys.exit(1)

    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    updated = []
    errors = []

    with engine.connect() as conn:
        # Schemas que possuem a tabela test_sessions
        r = conn.execute(text("""
            SELECT DISTINCT table_schema
            FROM information_schema.tables
            WHERE table_name = 'test_sessions'
            ORDER BY table_schema
        """))
        schemas = [row[0] for row in r]

        if not schemas:
            print("Nenhum schema com tabela test_sessions encontrado.")
            return

        print(f"Schemas com test_sessions: {', '.join(schemas)}")

        for schema in schemas:
            try:
                # Nome de schema seguro (evitar injection)
                if not (schema and isinstance(schema, str) and all(c.isalnum() or c in "_" for c in schema)):
                    print(f"  [{schema}] Ignorado (nome inválido).")
                    continue
                quoted_schema = f'"{schema}"'
                # Verificar se as colunas já existem
                check = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = :schema AND table_name = 'test_sessions'
                    AND column_name IN ('paused_at', 'total_paused_seconds')
                """), {"schema": schema})
                existing = {row[0] for row in check}

                if "paused_at" not in existing:
                    conn.execute(text(f"ALTER TABLE {quoted_schema}.test_sessions ADD COLUMN paused_at TIMESTAMP NULL"))
                    print(f"  [{schema}] Coluna paused_at adicionada.")
                else:
                    print(f"  [{schema}] paused_at já existe.")

                if "total_paused_seconds" not in existing:
                    conn.execute(text(
                        f"ALTER TABLE {quoted_schema}.test_sessions ADD COLUMN total_paused_seconds INTEGER NOT NULL DEFAULT 0"
                    ))
                    print(f"  [{schema}] Coluna total_paused_seconds adicionada.")
                else:
                    print(f"  [{schema}] total_paused_seconds já existe.")

                updated.append(schema)
            except Exception as e:
                errors.append((schema, str(e)))
                print(f"  [{schema}] ERRO: {e}")

    if errors:
        print(f"\nErros em {len(errors)} schema(s).")
        for schema, err in errors:
            print(f"  - {schema}: {err}")
    else:
        print(f"\nConcluído: {len(updated)} schema(s) verificados/atualizados.")

    engine.dispose()


if __name__ == "__main__":
    main()
