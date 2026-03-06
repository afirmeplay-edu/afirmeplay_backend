#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adiciona a tabela student_purchases da loja em todos os schemas city_* existentes.

O catálogo store_items fica só em public. As compras (student_purchases) ficam por tenant:
cada schema city_xxx tem sua própria tabela student_purchases, com FK para "{schema}".student
e para public.store_items.

Novos municípios já recebem student_purchases via city_schema_service. Este script
atualiza os schemas de cidade que foram criados antes da loja existir.

Uso (na raiz do projeto, com venv ativado):
  python scripts/add_store_student_purchases_to_city_schemas.py

Requer: DATABASE_URL em app/.env (ou variável de ambiente).
Requer: public.store_items já criada (flask db upgrade).
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


def _safe_schema_name(schema: str) -> bool:
    """Retorna True se o nome do schema é seguro (apenas alfanumérico e underscore)."""
    return (
        schema
        and isinstance(schema, str)
        and schema.startswith("city_")
        and all(c.isalnum() or c == "_" for c in schema)
    )


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERRO: Defina DATABASE_URL (em app/.env ou variável de ambiente).")
        sys.exit(1)

    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    created = []
    skipped = []
    errors = []

    with engine.connect() as conn:
        # Garantir que public.store_items existe
        r = conn.execute(text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'store_items'
        """))
        if not r.fetchone():
            print("ERRO: Tabela public.store_items não existe. Rode antes: flask db upgrade")
            sys.exit(1)

        # Schemas city_* que possuem a tabela student (são schemas de município)
        r = conn.execute(text("""
            SELECT DISTINCT table_schema
            FROM information_schema.tables
            WHERE table_schema LIKE 'city_%'
              AND table_name = 'student'
            ORDER BY table_schema
        """))
        schemas = [row[0] for row in r]

        if not schemas:
            print("Nenhum schema city_* com tabela student encontrado.")
            return

        print(f"Schemas city_* com student: {len(schemas)}")

        for schema in schemas:
            if not _safe_schema_name(schema):
                print(f"  [{schema}] Ignorado (nome inválido).")
                continue

            quoted = f'"{schema}"'

            try:
                # Verificar se student_purchases já existe
                r = conn.execute(text("""
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = :schema AND table_name = 'student_purchases'
                """), {"schema": schema})
                if r.fetchone():
                    skipped.append(schema)
                    print(f"  [{schema}] student_purchases já existe.")
                    continue

                # Criar tabela e índices (mesmo DDL do city_schema_service)
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {quoted}.student_purchases (
                        id VARCHAR PRIMARY KEY,
                        student_id VARCHAR REFERENCES {quoted}.student(id) ON DELETE CASCADE NOT NULL,
                        store_item_id VARCHAR REFERENCES public.store_items(id) ON DELETE CASCADE NOT NULL,
                        price_paid INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text(
                    f'COMMENT ON TABLE {quoted}.student_purchases IS \'Compras da loja por aluno\''
                ))
                conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS idx_student_purchases_student_id ON {quoted}.student_purchases(student_id)"
                ))
                conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS idx_student_purchases_store_item_id ON {quoted}.student_purchases(store_item_id)"
                ))
                conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS idx_student_purchases_created_at ON {quoted}.student_purchases(created_at)"
                ))
                created.append(schema)
                print(f"  [{schema}] student_purchases criada.")
            except Exception as e:
                errors.append((schema, str(e)))
                print(f"  [{schema}] ERRO: {e}")

    if errors:
        print(f"\nErros em {len(errors)} schema(s):")
        for schema, err in errors:
            print(f"  - {schema}: {err}")
    else:
        print(f"\nConcluído: {len(created)} tabela(s) criada(s), {len(skipped)} já existia(m).")

    engine.dispose()


if __name__ == "__main__":
    main()
