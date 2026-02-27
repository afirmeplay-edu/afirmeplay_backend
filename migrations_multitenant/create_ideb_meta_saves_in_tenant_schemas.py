# -*- coding: utf-8 -*-
"""
Cria a tabela ideb_meta_saves em todos os schemas city_xxx (tenant).
NÃO cria no schema public.

Execute da raiz do projeto:
    python migrations_multitenant/create_ideb_meta_saves_in_tenant_schemas.py
    python migrations_multitenant/create_ideb_meta_saves_in_tenant_schemas.py --dry-run

Requer DATABASE_URL no .env (ex.: app/.env).
"""

import os
import sys
import logging
import argparse
from datetime import datetime

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Carregar .env (mesmo padrão do 0001)
for env_path in ["app/.env", "../app/.env", os.path.join(os.path.dirname(__file__), "..", "app", ".env")]:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

DATABASE_URL = os.getenv("DATABASE_URL")

# SQL: mesma estrutura da migration, mas no schema do tenant. FK continua em public.city.
# NÃO usamos schema public.
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {schema}.ideb_meta_saves (
    id VARCHAR NOT NULL,
    city_id VARCHAR NOT NULL REFERENCES public.city(id) ON DELETE CASCADE,
    level VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_ideb_meta_saves_context UNIQUE (city_id, level)
);
"""
CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_ideb_meta_saves_context ON {schema}.ideb_meta_saves (city_id, level);
"""


def city_id_to_schema_name(city_id: str) -> str:
    """Converte city_id (UUID com hífens) no nome do schema (underscores)."""
    return f"city_{str(city_id).replace('-', '_')}"


def get_tenant_schemas(cursor) -> list:
    """Retorna lista de schemas city_xxx existentes (apenas tenants, nunca public)."""
    cursor.execute(
        """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name LIKE 'city\_%' ESCAPE '\\'
        ORDER BY schema_name
        """
    )
    return [row[0] for row in cursor.fetchall()]


def run(dry_run: bool = False):
    if not DATABASE_URL:
        logger.error("DATABASE_URL não definido. Configure no .env (ex.: app/.env).")
        sys.exit(1)

    logger.info("%sConectando ao banco...", "[DRY RUN] " if dry_run else "")
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    try:
        schemas = get_tenant_schemas(cursor)
        if not schemas:
            logger.warning("Nenhum schema city_xxx encontrado. Nada a fazer.")
            return

        logger.info("Encontrados %d schema(s) tenant: %s", len(schemas), ", ".join(schemas))

        for schema in schemas:
            if dry_run:
                logger.info("[DRY RUN] Criaria tabela ideb_meta_saves em %s", schema)
                continue

            logger.info("Criando ideb_meta_saves em %s...", schema)
            cursor.execute(CREATE_TABLE_SQL.format(schema=schema))
            cursor.execute(CREATE_INDEX_SQL.format(schema=schema))

        logger.info("Concluído. Tabela ideb_meta_saves NÃO foi criada no public.")
    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Cria tabela ideb_meta_saves em todos os schemas city_xxx. NÃO cria no public."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas lista o que seria feito, sem executar",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
