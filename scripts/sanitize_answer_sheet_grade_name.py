#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Preenche grade_name vazio em answer_sheet_gabaritos (tenant), sem alterar alunos/resultados.

Ordem de fallback:
1) Grade vinculada pela turma (class.grade.name)
2) Grade vinculada por grade_id (public.grade.name)
3) Prefixo do título (ex.: "8º ANO - ...")

Uso:
  venv/bin/python scripts/sanitize_answer_sheet_grade_name.py --city-id <UUID> --dry-run
  venv/bin/python scripts/sanitize_answer_sheet_grade_name.py --city-id <UUID>
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import create_app, db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.studentClass import Class
from app.models.grades import Grade
from app.utils.tenant_middleware import city_id_to_schema_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TITLE_GRADE_PATTERN = re.compile(r"^\s*([0-9]{1,2}\s*[º°o]?\s*ano)\b", re.IGNORECASE)


def _from_title(title: str) -> str:
    if not title:
        return ""
    m = TITLE_GRADE_PATTERN.search(title.strip())
    if not m:
        return ""
    value = m.group(1).strip()
    return value.upper().replace("ANO", "Ano")


def _resolve_grade_name(gabarito: AnswerSheetGabarito) -> str:
    if gabarito.class_id:
        class_obj = Class.query.get(gabarito.class_id)
        if class_obj and class_obj.grade_id:
            grade = Grade.query.get(class_obj.grade_id)
            if grade and grade.name:
                return grade.name.strip()
    if gabarito.grade_id:
        grade = Grade.query.get(gabarito.grade_id)
        if grade and grade.name:
            return grade.name.strip()
    return _from_title(gabarito.title or "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Saneia grade_name vazio em gabaritos de cartão.")
    parser.add_argument("--city-id", required=True, help="UUID da cidade (tenant).")
    parser.add_argument("--dry-run", action="store_true", help="Somente mostrar mudanças.")
    args = parser.parse_args()

    city_id = str(args.city_id).strip()
    if not city_id:
        parser.error("--city-id é obrigatório.")

    app = create_app()
    with app.app_context():
        schema = city_id_to_schema_name(city_id)
        db.session.execute(text(f'SET search_path TO "{schema}", public'))

        rows = (
            AnswerSheetGabarito.query.filter(
                (AnswerSheetGabarito.grade_name.is_(None)) | (AnswerSheetGabarito.grade_name == "")
            )
            .order_by(AnswerSheetGabarito.created_at.desc())
            .all()
        )
        logger.info("Gabaritos com grade_name vazio: %s", len(rows))

        updates = 0
        skipped = 0
        for g in rows:
            new_name = _resolve_grade_name(g)
            if not new_name:
                skipped += 1
                logger.info("SKIP gabarito=%s title=%r", g.id, g.title)
                continue
            logger.info("UPDATE gabarito=%s grade_name: %r -> %r", g.id, g.grade_name, new_name)
            if not args.dry_run:
                g.grade_name = new_name
                updates += 1

        if args.dry_run:
            logger.info("Dry-run concluído. Atualizações previstas=%s | skips=%s", updates or (len(rows) - skipped), skipped)
            return

        db.session.commit()
        logger.info("Saneamento concluído. Atualizados=%s | skips=%s", updates, skipped)


if __name__ == "__main__":
    main()
