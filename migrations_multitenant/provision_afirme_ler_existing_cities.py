# -*- coding: utf-8 -*-
"""
Aplica o DDL do Afirme Ler em schemas city_* JÁ EXISTENTES.

Inclui:
  - colunas novas em reading_evaluation_session (PLCM, ICA, etc.)
  - tabelas da leitura guiada / guiada automática (CREATE IF NOT EXISTS)

NÃO cria município novo. Só altera schemas que já existem.

Uso (na raiz do repositório):

  python migrations_multitenant/provision_afirme_ler_existing_cities.py
  python migrations_multitenant/provision_afirme_ler_existing_cities.py --dry-run
  python migrations_multitenant/provision_afirme_ler_existing_cities.py --schema city_9a2f95ed_9f70_4863_a5f1_1b6c6c262b0d

Requer DATABASE_URL em app/.env (ou ambiente).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import List

from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

log_filename = (
    f"provision_afirme_ler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

for env_path in (
    os.path.join(ROOT, "app", ".env"),
    "app/.env",
    os.path.join(os.path.dirname(__file__), "..", "app", ".env"),
):
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info("Arquivo .env carregado: %s", env_path)
        break


def list_city_schemas(db) -> List[str]:
    from sqlalchemy import text

    rows = db.session.execute(
        text(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name LIKE 'city_%'
            ORDER BY schema_name
            """
        )
    ).fetchall()
    return [row[0] for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Provisiona DDL Afirme Ler nos schemas city_* existentes "
            "(não cria município)."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas lista os schemas que seriam atualizados.",
    )
    parser.add_argument(
        "--schema",
        action="append",
        dest="schemas",
        help="Schema específico (pode repetir). Se omitido, processa todos city_*.",
    )
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        logger.error("DATABASE_URL não encontrado. Configure app/.env.")
        return 1

    from app import create_app, db
    from app.services.city_schema_service import provision_afirme_ler_for_city_schema

    app = create_app()
    ok = 0
    failed = 0

    with app.app_context():
        if args.schemas:
            schemas = args.schemas
            for schema in schemas:
                if not str(schema).startswith("city_"):
                    logger.error("Schema inválido (deve começar com city_): %s", schema)
                    return 1
        else:
            schemas = list_city_schemas(db)

        logger.info("Schemas a processar: %s", len(schemas))
        if not schemas:
            logger.warning("Nenhum schema city_* encontrado.")
            return 0

        for schema in schemas:
            if args.dry_run:
                logger.info("[DRY RUN] Aplicaria provision_afirme_ler em %s", schema)
                ok += 1
                continue
            try:
                provision_afirme_ler_for_city_schema(schema)
                logger.info("OK: Afirme Ler provisionado em %s", schema)
                ok += 1
            except Exception as exc:
                failed += 1
                logger.error("Falha em %s: %s", schema, exc, exc_info=True)

    logger.info("Resumo: ok=%s failed=%s log=%s", ok, failed, log_filename)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
