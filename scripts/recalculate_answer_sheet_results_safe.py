#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Recálculo seguro de resultados de cartão-resposta com backup e restore.

Objetivo:
- Recalcular campos derivados (nota, proficiência, classificação, etc.)
  em answer_sheet_results para um gabarito específico.
- Preservar dados originais com backup JSON antes da gravação.
- Permitir restore completo a partir do backup, se necessário.

Uso:
  python scripts/recalculate_answer_sheet_results_safe.py \
    --city-id <UUID_DA_CIDADE> \
    --gabarito-id <UUID_GABARITO> \
    --dry-run

  python scripts/recalculate_answer_sheet_results_safe.py \
    --city-id <UUID_DA_CIDADE> \
    --gabarito-id <UUID_GABARITO>

  python scripts/recalculate_answer_sheet_results_safe.py \
    --city-id <UUID_DA_CIDADE> \
    --restore-file scripts/backups/answer_sheet_results_backup_*.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import create_app, db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.report_analysis.answer_sheet_aggregate_service import (
    AnswerSheetReportAggregateService,
)
from app.services.cartao_resposta.proficiency_by_subject import (
    calcular_proficiencia_por_disciplina,
)
from app.utils.decimal_helpers import round_to_two_decimals
from app.utils.tenant_middleware import city_id_to_schema_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _normalize_alt(value: Any) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().upper()
    return v or None


def _parse_answer_map(raw: Any) -> Dict[int, Optional[str]]:
    payload = raw or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    out: Dict[int, Optional[str]] = {}
    for k, v in payload.items():
        try:
            q_num = int(k)
        except (TypeError, ValueError):
            continue
        out[q_num] = _normalize_alt(v)
    return out


def _build_correction_stats(
    detected_answers: Dict[int, Optional[str]],
    gabarito: Dict[int, Optional[str]],
) -> Dict[str, Any]:
    total_questions = len(gabarito)
    answered = 0
    correct = 0
    incorrect = 0
    unanswered = 0

    for q_num in sorted(gabarito.keys()):
        detected = _normalize_alt(detected_answers.get(q_num))
        correct_answer = _normalize_alt(gabarito.get(q_num))
        if not detected:
            unanswered += 1
            continue
        answered += 1
        if detected == correct_answer:
            correct += 1
        else:
            incorrect += 1

    score_percentage = (correct / total_questions * 100.0) if total_questions > 0 else 0.0
    return {
        "total_questions": total_questions,
        "answered": answered,
        "correct": correct,
        "incorrect": incorrect,
        "unanswered": unanswered,
        "score_percentage": round(score_percentage, 2),
    }


def _to_backup_row(result: AnswerSheetResult) -> Dict[str, Any]:
    return {
        "id": str(result.id),
        "gabarito_id": str(result.gabarito_id),
        "student_id": str(result.student_id),
        "detected_answers": result.detected_answers,
        "correct_answers": result.correct_answers,
        "total_questions": result.total_questions,
        "incorrect_answers": result.incorrect_answers,
        "unanswered_questions": result.unanswered_questions,
        "answered_questions": result.answered_questions,
        "score_percentage": result.score_percentage,
        "grade": result.grade,
        "proficiency": result.proficiency,
        "classification": result.classification,
        "proficiency_by_subject": result.proficiency_by_subject,
        "corrected_at": result.corrected_at.isoformat() if result.corrected_at else None,
        "detection_method": result.detection_method,
    }


def _write_backup(
    *,
    city_id: str,
    schema: str,
    gabarito_id: str,
    grade_name: str,
    rows: List[Dict[str, Any]],
    backup_dir: Path,
) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_name = f"answer_sheet_results_backup_{gabarito_id}_{ts}.json"
    backup_path = backup_dir / file_name
    payload = {
        "created_at_utc": datetime.utcnow().isoformat(),
        "city_id": city_id,
        "schema": schema,
        "gabarito_id": gabarito_id,
        "grade_name": grade_name,
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
        raise ValueError(
            f"Backup de outra cidade (backup={backup_city_id}, argumento={city_id})."
        )
    gabarito_id = str(payload.get("gabarito_id") or "").strip()
    if not gabarito_id:
        raise ValueError("Backup sem gabarito_id.")

    updated = 0
    missing = 0
    for row in rows:
        result_id = str(row.get("id") or "").strip()
        if not result_id:
            continue
        result = AnswerSheetResult.query.get(result_id)
        if not result:
            missing += 1
            continue

        result.detected_answers = row.get("detected_answers")
        result.correct_answers = row.get("correct_answers")
        result.total_questions = row.get("total_questions")
        result.incorrect_answers = row.get("incorrect_answers")
        result.unanswered_questions = row.get("unanswered_questions")
        result.answered_questions = row.get("answered_questions")
        result.score_percentage = row.get("score_percentage")
        result.grade = row.get("grade")
        result.proficiency = row.get("proficiency")
        result.classification = row.get("classification")
        result.proficiency_by_subject = row.get("proficiency_by_subject")
        result.detection_method = row.get("detection_method") or result.detection_method
        updated += 1

    db.session.commit()
    AnswerSheetReportAggregateService.mark_all_dirty_for_gabarito(gabarito_id, commit=True)
    logger.info("Restore concluído. Atualizados=%s | Não encontrados=%s", updated, missing)


def _recalculate_gabarito(
    gabarito_id: str,
    city_id: str,
    dry_run: bool,
    backup_dir: Path,
) -> Tuple[int, int, int, int, Path]:
    gabarito = AnswerSheetGabarito.query.get(gabarito_id)
    if not gabarito:
        raise ValueError(f"Gabarito não encontrado: {gabarito_id}")

    grade_name = (gabarito.grade_name or gabarito.title or "").strip()
    blocks_config = getattr(gabarito, "blocks_config", None) or {}
    if isinstance(blocks_config, str):
        try:
            blocks_config = json.loads(blocks_config) or {}
        except Exception:
            blocks_config = {}
    correct_map = _parse_answer_map(gabarito.correct_answers)
    if not correct_map:
        raise ValueError("Gabarito sem respostas válidas.")
    gabarito_dict = {k: (str(v).upper() if v else "") for k, v in correct_map.items()}

    results = AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id).all()
    if not results:
        raise ValueError("Nenhum resultado encontrado para o gabarito informado.")

    schema = city_id_to_schema_name(city_id)
    backup_rows = [_to_backup_row(r) for r in results]
    backup_path = _write_backup(
        city_id=city_id,
        schema=schema,
        gabarito_id=gabarito_id,
        grade_name=grade_name,
        rows=backup_rows,
        backup_dir=backup_dir,
    )

    changed = 0
    unchanged = 0
    classification_changed = 0
    total = len(results)

    for result in results:
        detected_map = _parse_answer_map(result.detected_answers)
        stats = _build_correction_stats(detected_map, correct_map)
        pbs, prof_media, grade_geral, class_geral, _has_matematica = calcular_proficiencia_por_disciplina(
            blocks_config=blocks_config,
            validated_answers=detected_map,
            gabarito_dict=gabarito_dict,
            grade_name=grade_name,
        )
        grade_geral = round_to_two_decimals(float(grade_geral))
        prof_media = round_to_two_decimals(float(prof_media)) if prof_media is not None else None

        old_tuple = (
            result.correct_answers,
            result.total_questions,
            result.incorrect_answers,
            result.unanswered_questions,
            result.answered_questions,
            round(float(result.score_percentage or 0.0), 2),
            round(float(result.grade or 0.0), 2),
            round(float(result.proficiency or 0.0), 2) if result.proficiency is not None else None,
            result.classification,
            result.proficiency_by_subject,
        )
        new_tuple = (
            stats["correct"],
            stats["total_questions"],
            stats["incorrect"],
            stats["unanswered"],
            stats["answered"],
            round(float(stats["score_percentage"]), 2),
            round(float(grade_geral), 2),
            round(float(prof_media), 2) if prof_media is not None else None,
            class_geral,
            pbs,
        )

        if old_tuple != new_tuple:
            changed += 1
            if (result.classification or "") != (class_geral or ""):
                classification_changed += 1
        else:
            unchanged += 1

        if dry_run:
            continue

        result.correct_answers = stats["correct"]
        result.total_questions = stats["total_questions"]
        result.incorrect_answers = stats["incorrect"]
        result.unanswered_questions = stats["unanswered"]
        result.answered_questions = stats["answered"]
        result.score_percentage = stats["score_percentage"]
        result.grade = grade_geral
        result.proficiency = prof_media
        result.classification = class_geral
        result.proficiency_by_subject = pbs

    if not dry_run:
        db.session.commit()
        AnswerSheetReportAggregateService.mark_all_dirty_for_gabarito(gabarito_id, commit=True)

    return total, changed, unchanged, classification_changed, backup_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recálculo seguro de answer_sheet_results com backup e restore."
    )
    parser.add_argument("--city-id", required=True, help="UUID da cidade (tenant).")
    parser.add_argument("--gabarito-id", help="UUID do gabarito para recálculo.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula e gera backup, sem persistir alterações.",
    )
    parser.add_argument(
        "--backup-dir",
        default="scripts/backups",
        help="Diretório para salvar backup JSON (default: scripts/backups).",
    )
    parser.add_argument(
        "--restore-file",
        default=None,
        help="Arquivo de backup JSON para restaurar resultados.",
    )
    args = parser.parse_args()

    city_id = str(args.city_id).strip()
    if not city_id:
        parser.error("--city-id é obrigatório.")

    has_recalc = bool(args.gabarito_id and str(args.gabarito_id).strip())
    has_restore = bool(args.restore_file and str(args.restore_file).strip())
    if has_recalc == has_restore:
        parser.error("Informe exatamente um: --gabarito-id OU --restore-file.")

    app = create_app()
    with app.app_context():
        schema = city_id_to_schema_name(city_id)
        db.session.execute(text(f'SET search_path TO "{schema}", public'))

        if has_restore:
            restore_file = Path(str(args.restore_file).strip())
            if not restore_file.exists():
                raise FileNotFoundError(f"Arquivo de backup não encontrado: {restore_file}")
            _restore_from_backup(restore_file, city_id)
            logger.info("Restore finalizado com sucesso.")
            return

        gabarito_id = str(args.gabarito_id).strip()
        total, changed, unchanged, class_changed, backup_path = _recalculate_gabarito(
            gabarito_id=gabarito_id,
            city_id=city_id,
            dry_run=bool(args.dry_run),
            backup_dir=Path(str(args.backup_dir).strip()),
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
