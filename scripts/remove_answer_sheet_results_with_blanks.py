#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Remove resultados de cartão-resposta (AnswerSheetResult) de alunos que deixaram
pelo menos uma questão em branco (resposta ausente, null ou string vazia).

- Não apaga alunos; apenas remove o registro de correção.
- Gera backup JSON antes de apagar (restaurável com --restore-file).
- Marca agregados de relatório do gabarito como dirty.

Uso:
  ./venv/bin/python scripts/remove_answer_sheet_results_with_blanks.py \\
    --city-id <UUID_CIDADE> --dry-run

  ./venv/bin/python scripts/remove_answer_sheet_results_with_blanks.py \\
    --city-id <UUID_CIDADE>

  ./venv/bin/python scripts/remove_answer_sheet_results_with_blanks.py \\
    --city-id <UUID_CIDADE> --gabarito-id <UUID>

  ./venv/bin/python scripts/remove_answer_sheet_results_with_blanks.py \\
    --city-id <UUID_CIDADE> \\
    --restore-file scripts/backups/remove_blanks_*.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import create_app, db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.report_analysis.answer_sheet_aggregate_service import (
    AnswerSheetReportAggregateService,
)
from app.utils.tenant_middleware import city_id_to_schema_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

OPERATION = "remove_results_with_blank_questions"


def _parse_json_field(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _get_answer_for_question(detected: Dict[Any, Any], q_num: int) -> Any:
    if not detected:
        return None
    return detected.get(q_num, detected.get(str(q_num)))


def _is_blank_response(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _effective_num_questions(gab: AnswerSheetGabarito) -> int:
    n = int(gab.num_questions or 0)
    if n > 0:
        return n
    ca = _parse_json_field(gab.correct_answers) or {}
    keys: List[int] = []
    for k in ca.keys():
        try:
            keys.append(int(k))
        except (TypeError, ValueError):
            continue
    return max(keys) if keys else 0


def result_has_blank_question(result: AnswerSheetResult, gab: AnswerSheetGabarito) -> bool:
    """True se alguma questão esperada (1..N) está em branco nas respostas detectadas."""
    n = _effective_num_questions(gab)
    if n <= 0:
        return False
    det = _parse_json_field(result.detected_answers) or {}
    if not isinstance(det, dict):
        return True
    for q in range(1, n + 1):
        if _is_blank_response(_get_answer_for_question(det, q)):
            return True
    return False


def _row_to_backup(result: AnswerSheetResult) -> Dict[str, Any]:
    return {
        "id": str(result.id),
        "gabarito_id": str(result.gabarito_id),
        "student_id": str(result.student_id),
        "detected_answers": result.detected_answers,
        "correct_answers": int(result.correct_answers or 0),
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
    rows: List[Dict[str, Any]],
    backup_dir: Path,
) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = backup_dir / f"remove_blanks_{OPERATION}_{city_id[:8]}_{ts}.json"
    payload = {
        "operation": OPERATION,
        "created_at_utc": datetime.utcnow().isoformat(),
        "city_id": city_id,
        "schema": schema,
        "results_count": len(rows),
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _restore_from_backup(restore_file: Path, city_id: str) -> None:
    payload = json.loads(restore_file.read_text(encoding="utf-8"))
    if str(payload.get("operation") or "") != OPERATION:
        raise ValueError(
            f"Backup não é deste script (operation={payload.get('operation')!r})."
        )
    backup_city = str(payload.get("city_id") or "").strip()
    if backup_city and backup_city != city_id:
        raise ValueError(
            f"Backup de outra cidade (backup={backup_city}, argumento={city_id})."
        )
    rows = payload.get("rows") or []
    restored = 0
    gabaritos: Set[str] = set()
    for row in rows:
        rid = str(row.get("id") or "").strip()
        if not rid:
            continue
        if AnswerSheetResult.query.get(rid):
            continue
        corrected_at = row.get("corrected_at")
        ca_dt = None
        if corrected_at:
            try:
                ca_dt = datetime.fromisoformat(str(corrected_at).replace("Z", "+00:00"))
            except ValueError:
                ca_dt = None
        r = AnswerSheetResult(
            id=rid,
            gabarito_id=str(row["gabarito_id"]),
            student_id=str(row["student_id"]),
            detected_answers=row.get("detected_answers") or {},
            correct_answers=row.get("correct_answers", 0),
            total_questions=int(row.get("total_questions") or 0),
            incorrect_answers=int(row.get("incorrect_answers") or 0),
            unanswered_questions=int(row.get("unanswered_questions") or 0),
            answered_questions=int(row.get("answered_questions") or 0),
            score_percentage=float(row.get("score_percentage") or 0.0),
            grade=float(row.get("grade") or 0.0),
            proficiency=row.get("proficiency"),
            classification=row.get("classification"),
            proficiency_by_subject=row.get("proficiency_by_subject"),
            detection_method=row.get("detection_method") or "geometric",
        )
        if ca_dt is not None:
            r.corrected_at = ca_dt
        db.session.add(r)
        restored += 1
        gabaritos.add(str(row["gabarito_id"]))
    db.session.commit()
    for gid in gabaritos:
        AnswerSheetReportAggregateService.mark_all_dirty_for_gabarito(gid, commit=True)
    logger.info("Restore: recriados=%s | gabaritos afetados=%s", restored, len(gabaritos))


def collect_results_to_remove(
    gabarito_id_filter: Optional[str],
) -> List[Tuple[AnswerSheetResult, AnswerSheetGabarito]]:
    q = AnswerSheetResult.query
    if gabarito_id_filter:
        q = q.filter_by(gabarito_id=str(gabarito_id_filter).strip())
    pairs: List[Tuple[AnswerSheetResult, AnswerSheetGabarito]] = []
    for result in q.all():
        gab = AnswerSheetGabarito.query.get(result.gabarito_id)
        if not gab:
            logger.warning("Resultado %s: gabarito %s não encontrado, ignorando.", result.id, result.gabarito_id)
            continue
        if result_has_blank_question(result, gab):
            pairs.append((result, gab))
    return pairs


def run_remove(
    city_id: str,
    dry_run: bool,
    gabarito_id: Optional[str],
    backup_dir: Path,
) -> Tuple[int, Path]:
    schema = city_id_to_schema_name(city_id)
    pairs = collect_results_to_remove(gabarito_id)
    if not pairs:
        logger.info("Nenhum resultado com questão em branco encontrado.")
        path = _write_backup(city_id=city_id, schema=schema, rows=[], backup_dir=backup_dir)
        return 0, path

    rows = [_row_to_backup(r) for r, _ in pairs]
    backup_path = _write_backup(city_id=city_id, schema=schema, rows=rows, backup_dir=backup_dir)
    logger.info("Backup: %s (%s linhas)", backup_path, len(rows))

    gabaritos: Set[str] = set()
    for result, _ in pairs:
        gabaritos.add(str(result.gabarito_id))

    if dry_run:
        logger.info(
            "Dry-run: seriam removidos %s resultados em %s gabarito(s). IDs: %s",
            len(pairs),
            len(gabaritos),
            sorted(gabaritos),
        )
        return len(pairs), backup_path

    for result, _ in pairs:
        db.session.delete(result)
    db.session.commit()

    for gid in gabaritos:
        AnswerSheetReportAggregateService.mark_all_dirty_for_gabarito(gid, commit=True)

    logger.info(
        "Removidos %s resultados; gabaritos com cache invalidado: %s",
        len(pairs),
        len(gabaritos),
    )
    return len(pairs), backup_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove AnswerSheetResult com pelo menos uma questão em branco."
    )
    parser.add_argument("--city-id", required=True, help="UUID da cidade (tenant / schema).")
    parser.add_argument(
        "--gabarito-id",
        default=None,
        help="Opcional: apenas este gabarito. Sem isso, todos os resultados do schema.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Só lista e gera backup, não apaga.")
    parser.add_argument(
        "--backup-dir",
        default="scripts/backups",
        help="Diretório do backup JSON.",
    )
    parser.add_argument(
        "--restore-file",
        default=None,
        help="Restaurar linhas apagadas a partir do backup deste script.",
    )
    args = parser.parse_args()

    city_id = str(args.city_id).strip()
    has_restore = bool(args.restore_file and str(args.restore_file).strip())

    app = create_app()
    with app.app_context():
        schema = city_id_to_schema_name(city_id)
        db.session.execute(text(f'SET search_path TO "{schema}", public'))

        if has_restore:
            p = Path(str(args.restore_file).strip())
            if not p.exists():
                raise FileNotFoundError(p)
            _restore_from_backup(p, city_id)
            logger.info("Restore concluído.")
            return

        n, path = run_remove(
            city_id=city_id,
            dry_run=bool(args.dry_run),
            gabarito_id=str(args.gabarito_id).strip() if args.gabarito_id else None,
            backup_dir=Path(str(args.backup_dir).strip()),
        )
        if args.dry_run:
            logger.info("Dry-run finalizado. Backup em %s", path)
        else:
            logger.info("Concluído. Removidos=%s. Backup=%s", n, path)


if __name__ == "__main__":
    main()
