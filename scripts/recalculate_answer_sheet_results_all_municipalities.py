#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Recalcula APENAS cartões-resposta: tabela answer_sheet_results (schemas city_*).

Não altera em hipótese alguma: evaluation_results, tests, student_answers, questions,
nem qualquer dado de avaliação online — somente linhas de AnswerSheetResult e agregados
de relatório de cartão (mark_all_dirty) ligados ao gabarito.

Critério de cálculo (alinhado à regra de média usada em evaluation_results para notas
consolidadas: valores persistidos no resultado; grade geral = média das notas por
disciplina quando há blocos):
- proficiency: média das proficiências por disciplina
- grade: média das notas por disciplina
- classification: a partir da proficiência média (GERAL / has_matematica) no serviço
- proficiency_by_subject: calcular_proficiencia_por_disciplina
- Acertos / score_percentage: a partir de detected_answers vs gabarito

Comportamento:
- Itera schemas city_* existentes no PostgreSQL.
- Para cada schema: define search_path, busca gabaritos distintos com resultados.
- Se não houver resultados no município, pula.
- Se um gabarito não tiver respostas corretas, pula com aviso.
- Opcional: --dry-run não grava.

Uso (na raiz do projeto, venv ativo, DATABASE_URL em app/.env):

  python scripts/recalculate_answer_sheet_results_all_municipalities.py --dry-run
  python scripts/recalculate_answer_sheet_results_all_municipalities.py

  # Apenas um tenant (teste):
  python scripts/recalculate_answer_sheet_results_all_municipalities.py --schema city_0f93f076_c274_4515_98df_302bbf7e9b15
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
from app.report_analysis.answer_sheet_aggregate_service import AnswerSheetReportAggregateService
from app.services.cartao_resposta.proficiency_by_subject import calcular_proficiencia_por_disciplina
from app.utils.decimal_helpers import round_to_two_decimals

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


def _parse_blocks_config(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            return json.loads(raw) or {}
        except Exception:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


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


def _recalculate_one_result(
    result: AnswerSheetResult,
    correct_map: Dict[int, Optional[str]],
    blocks_config: Dict[str, Any],
    grade_name: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Retorna (stats, novos_campos) onde novos_campos tem keys:
    grade, proficiency, classification, proficiency_by_subject, + stats numéricos.
    """
    detected_map = _parse_answer_map(result.detected_answers)
    stats = _build_correction_stats(detected_map, correct_map)

    # Gabarito: mesmas chaves que correct_map; valores em maiúsculas (como no fluxo de correção)
    gabarito_dict: Dict[int, str] = {}
    for k, v in correct_map.items():
        gabarito_dict[k] = str(v).upper() if v else ""

    pbs, prof_media, grade_media, class_geral, _has_mat = calcular_proficiencia_por_disciplina(
        blocks_config=blocks_config,
        validated_answers=detected_map,
        gabarito_dict=gabarito_dict,
        grade_name=grade_name,
    )

    # Serializar JSON-friendly (floats)
    pbs_out = pbs
    new_fields = {
        "correct_answers": stats["correct"],
        "total_questions": stats["total_questions"],
        "incorrect_answers": stats["incorrect"],
        "unanswered_questions": stats["unanswered"],
        "answered_questions": stats["answered"],
        "score_percentage": stats["score_percentage"],
        "grade": round_to_two_decimals(float(grade_media)),
        "proficiency": round_to_two_decimals(float(prof_media)) if prof_media is not None else None,
        "classification": class_geral,
        "proficiency_by_subject": pbs_out,
    }
    return stats, new_fields


def _row_changed(result: AnswerSheetResult, new_fields: Dict[str, Any]) -> bool:
    def _close(a, b, tol=0.01):
        try:
            return abs(float(a or 0) - float(b or 0)) <= tol
        except (TypeError, ValueError):
            return (a or None) == (b or None)

    if result.correct_answers != new_fields["correct_answers"]:
        return True
    if result.total_questions != new_fields["total_questions"]:
        return True
    if result.incorrect_answers != new_fields["incorrect_answers"]:
        return True
    if result.unanswered_questions != new_fields["unanswered_questions"]:
        return True
    if result.answered_questions != new_fields["answered_questions"]:
        return True
    if not _close(result.score_percentage, new_fields["score_percentage"], 0.02):
        return True
    if not _close(result.grade, new_fields["grade"]):
        return True
    if not _close(result.proficiency, new_fields["proficiency"]):
        return True
    if (result.classification or "") != (new_fields["classification"] or ""):
        return True
    old_pbs = result.proficiency_by_subject
    if isinstance(old_pbs, str):
        try:
            old_pbs = json.loads(old_pbs)
        except Exception:
            old_pbs = None
    try:
        if json.dumps(old_pbs or {}, sort_keys=True) != json.dumps(
            new_fields["proficiency_by_subject"] or {}, sort_keys=True
        ):
            return True
    except TypeError:
        return True
    return False


def _process_gabarito(
    gabarito_id: str,
    dry_run: bool,
) -> Tuple[int, int, int]:
    """
    Retorna (total_resultados, atualizados, inalterados).
    """
    gab = AnswerSheetGabarito.query.get(gabarito_id)
    if not gab:
        logger.warning("Gabarito %s não encontrado (schema atual); ignorado.", gabarito_id)
        return 0, 0, 0

    grade_name = (gab.grade_name or gab.title or "").strip()
    blocks_config = _parse_blocks_config(getattr(gab, "blocks_config", None))
    correct_map = _parse_answer_map(gab.correct_answers)
    if not correct_map:
        logger.warning("Gabarito %s sem correct_answers; ignorado.", gabarito_id)
        return 0, 0, 0

    results: List[AnswerSheetResult] = AnswerSheetResult.query.filter_by(
        gabarito_id=gabarito_id
    ).all()
    if not results:
        return 0, 0, 0

    updated = 0
    unchanged = 0
    for result in results:
        try:
            _, new_fields = _recalculate_one_result(
                result, correct_map, blocks_config, grade_name
            )
        except Exception as exc:
            logger.exception(
                "Erro ao recalcular result id=%s gabarito=%s: %s",
                result.id,
                gabarito_id,
                exc,
            )
            continue

        if not _row_changed(result, new_fields):
            unchanged += 1
            continue

        updated += 1
        if dry_run:
            continue

        result.correct_answers = new_fields["correct_answers"]
        result.total_questions = new_fields["total_questions"]
        result.incorrect_answers = new_fields["incorrect_answers"]
        result.unanswered_questions = new_fields["unanswered_questions"]
        result.answered_questions = new_fields["answered_questions"]
        result.score_percentage = new_fields["score_percentage"]
        result.grade = new_fields["grade"]
        result.proficiency = new_fields["proficiency"]
        result.classification = new_fields["classification"]
        result.proficiency_by_subject = new_fields["proficiency_by_subject"]

    if not dry_run and updated:
        db.session.commit()
        try:
            AnswerSheetReportAggregateService.mark_all_dirty_for_gabarito(gabarito_id, commit=True)
        except Exception as exc:
            logger.warning("mark_all_dirty gabarito=%s: %s", gabarito_id, exc)

    return len(results), updated, unchanged


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recalcula answer_sheet_results em todos os municípios (schemas city_*)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula sem gravar alterações.",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Processar apenas um schema (ex.: city_0f93f076_c274_4515_98df_302bbf7e9b15).",
    )
    args = parser.parse_args()

    app = create_app()
    dry_run = bool(args.dry_run)

    total_schemas = 0
    skipped_empty_schema = 0
    total_results = 0
    total_updated = 0
    total_unchanged = 0
    total_gabaritos = 0

    with app.app_context():
        schemas = _list_city_schemas(args.schema)

        if not schemas:
            logger.info("Nenhum schema city_* para processar.")
            return

        logger.info(
            "Início recálculo | schemas=%s | dry_run=%s | %s",
            len(schemas),
            dry_run,
            datetime.utcnow().isoformat(),
        )

        for schema in schemas:
            total_schemas += 1
            db.session.execute(text(f'SET search_path TO "{schema}", public'))

            # Distinct gabaritos com pelo menos um resultado
            rows = db.session.execute(
                text(
                    """
                    SELECT DISTINCT gabarito_id
                    FROM answer_sheet_results
                    """
                )
            ).fetchall()
            gabarito_ids = [str(r[0]) for r in rows if r[0]]
            if not gabarito_ids:
                skipped_empty_schema += 1
                logger.info("[%s] Sem answer_sheet_results; pulando.", schema)
                db.session.rollback()
                continue

            logger.info("[%s] %s gabarito(s) com resultados.", schema, len(gabarito_ids))

            for gid in gabarito_ids:
                total_gabaritos += 1
                n_res, n_upd, n_same = _process_gabarito(gid, dry_run=dry_run)
                total_results += n_res
                total_updated += n_upd
                total_unchanged += n_same
                if n_res:
                    logger.info(
                        "  gabarito=%s | resultados=%s | atualizados=%s | sem_mudança=%s",
                        gid,
                        n_res,
                        n_upd,
                        n_same,
                    )

            db.session.commit()

    logger.info(
        "Fim | schemas_processados=%s | schemas_sem_dados=%s | gabaritos=%s | "
        "linhas_resultado=%s | atualizados=%s | inalterados=%s | dry_run=%s",
        total_schemas,
        skipped_empty_schema,
        total_gabaritos,
        total_results,
        total_updated,
        total_unchanged,
        dry_run,
    )
    if dry_run:
        logger.info("Dry-run: nenhuma alteração foi persistida. Rode sem --dry-run para aplicar.")


if __name__ == "__main__":
    main()
