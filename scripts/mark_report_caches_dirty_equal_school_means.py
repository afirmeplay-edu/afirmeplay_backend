#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Marca caches de relatório agregado como dirty após alteração da regra de médias
consolidadas (peso igual por escola). Na próxima leitura, o rebuild recalcula com a nova lógica.

- Por schema ``city_*``: chama ``AnswerSheetReportAggregateService.mark_all_dirty_for_gabarito``
  para cada gabarito que tenha linhas em ``answer_sheet_report_aggregates`` ou
  ``answer_sheet_results`` (união).
- Opcional ``--include-public-evaluation-tests``: ``ReportAggregateService.mark_all_dirty_for_test``
  para cada ``test_id`` distinto em ``public.report_aggregates``.

Uso (venv ativo, ``DATABASE_URL`` em ``app/.env``):

  python scripts/mark_report_caches_dirty_equal_school_means.py --dry-run
  python scripts/mark_report_caches_dirty_equal_school_means.py
  python scripts/mark_report_caches_dirty_equal_school_means.py --schema city_0f93f076_c274_4515_98df_302bbf7e9b15
  python scripts/mark_report_caches_dirty_equal_school_means.py --include-public-evaluation-tests
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import create_app, db
from app.report_analysis.answer_sheet_aggregate_service import AnswerSheetReportAggregateService
from app.services.report_aggregate_service import ReportAggregateService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _safe_schema_name(schema: str) -> bool:
    return bool(
        schema
        and isinstance(schema, str)
        and schema.startswith("city_")
        and all(c.isalnum() or c == "_" for c in schema)
    )


def _list_city_schemas(single: Optional[str]) -> List[str]:
    if single:
        s = single.strip()
        if not _safe_schema_name(s):
            raise ValueError(f"Schema inválido ou inseguro: {single}")
        r = db.session.execute(
            text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"),
            {"s": s},
        )
        if not r.fetchone():
            raise ValueError(f"Schema não existe: {s}")
        return [s]

    r = db.session.execute(
        text(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name LIKE 'city_%'
            ORDER BY schema_name
            """
        )
    )
    return [row[0] for row in r if _safe_schema_name(row[0])]


def _gabarito_ids_for_schema() -> List[str]:
    rows = db.session.execute(
        text(
            """
            SELECT gabarito_id FROM answer_sheet_report_aggregates
            UNION
            SELECT gabarito_id FROM answer_sheet_results
            """
        )
    ).fetchall()
    out = []
    for r in rows:
        if r[0]:
            out.append(str(r[0]))
    return sorted(set(out))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Marca caches de relatório (cartão / opcional avaliação online) como dirty."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas regista o que seria feito, sem gravar.",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Processar apenas um schema city_*.",
    )
    parser.add_argument(
        "--include-public-evaluation-tests",
        action="store_true",
        help="Também marcar dirty todos os test_id em public.report_aggregates.",
    )
    args = parser.parse_args()
    dry_run = bool(args.dry_run)

    app = create_app()
    total_gabaritos = 0
    total_tests = 0

    with app.app_context():
        schemas = _list_city_schemas(args.schema)
        if not schemas:
            logger.info("Nenhum schema city_* para processar.")
        else:
            logger.info(
                "Início mark dirty (cartão) | schemas=%s | dry_run=%s | %s",
                len(schemas),
                dry_run,
                datetime.utcnow().isoformat(),
            )

        for schema in schemas:
            db.session.execute(text(f'SET search_path TO "{schema}", public'))
            gids = _gabarito_ids_for_schema()
            if not gids:
                logger.info("[%s] Nenhum gabarito em agregados/resultados; pulando.", schema)
                db.session.rollback()
                continue
            logger.info("[%s] %s gabarito(s) a marcar dirty.", schema, len(gids))
            for gid in gids:
                total_gabaritos += 1
                if dry_run:
                    logger.info("  [dry-run] mark_all_dirty gabarito_id=%s", gid)
                    continue
                try:
                    AnswerSheetReportAggregateService.mark_all_dirty_for_gabarito(gid, commit=True)
                except Exception as exc:
                    logger.warning("mark_all_dirty gabarito=%s: %s", gid, exc)

        if args.include_public_evaluation_tests:
            db.session.execute(text("SET search_path TO public"))
            rows = db.session.execute(
                text("SELECT DISTINCT test_id FROM report_aggregates WHERE test_id IS NOT NULL")
            ).fetchall()
            test_ids = [str(r[0]) for r in rows if r[0]]
            logger.info(
                "Relatórios avaliação online (public): %s test_id(s) | dry_run=%s",
                len(test_ids),
                dry_run,
            )
            for tid in test_ids:
                total_tests += 1
                if dry_run:
                    logger.info("  [dry-run] mark_all_dirty_for_test test_id=%s", tid)
                    continue
                try:
                    ReportAggregateService.mark_all_dirty_for_test(tid, commit=True)
                except Exception as exc:
                    logger.warning("mark_all_dirty_for_test test_id=%s: %s", tid, exc)

    logger.info(
        "Fim | gabaritos_processados=%s | testes_public=%s | dry_run=%s",
        total_gabaritos,
        total_tests,
        dry_run,
    )
    if dry_run:
        logger.info("Dry-run: nada foi persistido. Rode sem --dry-run para aplicar.")


if __name__ == "__main__":
    main()
