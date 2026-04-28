#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Recálculo seguro de resultados de avaliação ONLINE (evaluation_results) para um teste específico.

Objetivo:
- Recalcular campos derivados (grade, proficiency, classification, subject_results, score_percentage)
  em `evaluation_results` para um `test_id` específico, usando a regra:
  - denominador = total de questões (geral) e total de questões da disciplina (por disciplina)
  - questões em branco contam como erradas
- Preservar dados originais com backup JSON antes da gravação.

Uso:
  python scripts/recalculate_test_evaluation_results_safe.py --city-id <UUID_CIDADE> --test-id <UUID_TESTE> --dry-run
  python scripts/recalculate_test_evaluation_results_safe.py --city-id <UUID_CIDADE> --test-id <UUID_TESTE>

Restore:
  python scripts/recalculate_test_evaluation_results_safe.py --city-id <UUID_CIDADE> --restore-file scripts/backups/evaluation_results_backup_<...>.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import create_app, db
from app.models.evaluationResult import EvaluationResult
from app.report_analysis.answer_sheet_aggregate_service import AnswerSheetReportAggregateService  # noqa: F401
from app.services.evaluation_result_service import EvaluationResultService
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _to_backup_row(r: EvaluationResult) -> Dict[str, Any]:
    return {
        "id": str(r.id),
        "test_id": str(r.test_id),
        "student_id": str(r.student_id),
        "session_id": str(r.session_id),
        "correct_answers": r.correct_answers,
        "total_questions": r.total_questions,
        "score_percentage": r.score_percentage,
        "grade": r.grade,
        "proficiency": r.proficiency,
        "classification": r.classification,
        "subject_results": r.subject_results,
        "calculated_at": r.calculated_at.isoformat() if getattr(r, "calculated_at", None) else None,
    }


def _write_backup(
    *,
    city_id: str,
    schema: str,
    test_id: str,
    rows: List[Dict[str, Any]],
    backup_dir: Path,
) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_name = f"evaluation_results_backup_{test_id}_{ts}.json"
    backup_path = backup_dir / file_name
    payload = {
        "created_at_utc": datetime.utcnow().isoformat(),
        "city_id": city_id,
        "schema": schema,
        "test_id": test_id,
        "results_count": len(rows),
        "rows": rows,
    }
    backup_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_path


def _restore_from_backup(restore_file: Path, city_id: str) -> None:
    payload = json.loads(restore_file.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    backup_city_id = str(payload.get("city_id") or "").strip()
    if backup_city_id and backup_city_id != city_id:
        raise ValueError(f"Backup de outra cidade (backup={backup_city_id}, argumento={city_id}).")

    updated = 0
    missing = 0
    for row in rows:
        result_id = str(row.get("id") or "").strip()
        if not result_id:
            continue
        r = EvaluationResult.query.get(result_id)
        if not r:
            missing += 1
            continue
        r.correct_answers = row.get("correct_answers", r.correct_answers)
        r.total_questions = row.get("total_questions", r.total_questions)
        r.score_percentage = row.get("score_percentage", r.score_percentage)
        r.grade = row.get("grade", r.grade)
        r.proficiency = row.get("proficiency", r.proficiency)
        r.classification = row.get("classification", r.classification)
        r.subject_results = row.get("subject_results", r.subject_results)
        updated += 1

    db.session.commit()
    logger.info("Restore concluído. Atualizados=%s | Não encontrados=%s", updated, missing)


def _recalculate_test(
    *,
    test_id: str,
    dry_run: bool,
    backup_dir: Path,
    city_id: str,
) -> Tuple[int, int, int, int, Path]:
    results = EvaluationResult.query.filter_by(test_id=test_id).all()
    if not results:
        raise ValueError("Nenhum EvaluationResult encontrado para o test_id informado.")

    schema = city_id_to_schema_name(city_id)
    backup_path = _write_backup(
        city_id=city_id,
        schema=schema,
        test_id=test_id,
        rows=[_to_backup_row(r) for r in results],
        backup_dir=backup_dir,
    )

    changed = 0
    unchanged = 0
    classification_changed = 0
    total = len(results)

    for r in results:
        old = (r.correct_answers, r.total_questions, r.score_percentage, r.grade, r.proficiency, r.classification, r.subject_results)

        # Recalcula usando o serviço central (agora corrigido para denominador total por disciplina)
        new_payload = EvaluationResultService.calculate_and_save_result(
            test_id=str(r.test_id),
            student_id=str(r.student_id),
            session_id=str(r.session_id),
        )
        if not new_payload:
            logger.warning("Falha ao recalcular evaluation_result=%s (student=%s)", r.id, r.student_id)
            continue

        db.session.flush()
        db.session.refresh(r)

        new = (r.correct_answers, r.total_questions, r.score_percentage, r.grade, r.proficiency, r.classification, r.subject_results)
        if new != old:
            changed += 1
            if (old[5] or "") != (new[5] or ""):
                classification_changed += 1
        else:
            unchanged += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return total, changed, unchanged, classification_changed, backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Recálculo seguro de evaluation_results por test_id.")
    parser.add_argument("--city-id", required=True, help="UUID da cidade (tenant).")
    parser.add_argument("--test-id", help="UUID do teste para recálculo.")
    parser.add_argument("--dry-run", action="store_true", help="Simula e gera backup, sem gravar alterações.")
    parser.add_argument("--backup-dir", default="scripts/backups", help="Diretório para salvar backups JSON.")
    parser.add_argument("--restore-file", default=None, help="Arquivo de backup JSON para restaurar resultados.")
    args = parser.parse_args()

    city_id = str(args.city_id).strip()
    has_recalc = bool(args.test_id and str(args.test_id).strip())
    has_restore = bool(args.restore_file and str(args.restore_file).strip())
    if has_recalc == has_restore:
        parser.error("Informe exatamente um: --test-id OU --restore-file.")

    app = create_app()
    with app.app_context():
        schema = city_id_to_schema_name(city_id)
        set_search_path(schema)

        if has_restore:
            restore_file = Path(str(args.restore_file).strip())
            if not restore_file.exists():
                raise FileNotFoundError(f"Arquivo de backup não encontrado: {restore_file}")
            _restore_from_backup(restore_file, city_id)
            logger.info("Restore finalizado com sucesso.")
            return

        test_id = str(args.test_id).strip()
        total, changed, unchanged, class_changed, backup_path = _recalculate_test(
            test_id=test_id,
            dry_run=bool(args.dry_run),
            backup_dir=Path(str(args.backup_dir).strip()),
            city_id=city_id,
        )

        logger.info("Backup salvo em: %s", backup_path)
        logger.info(
            "Resumo: total=%s | alterados=%s | inalterados=%s | classificação_alterada=%s",
            total,
            changed,
            unchanged,
            class_changed,
        )
        if args.dry_run:
            logger.info("Dry-run ativo: nenhuma alteração foi gravada no banco.")
            logger.info("Para aplicar, rode novamente sem --dry-run.")
        else:
            logger.info("Recálculo concluído e gravado com sucesso.")


if __name__ == "__main__":
    main()

