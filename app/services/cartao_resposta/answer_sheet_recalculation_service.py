# -*- coding: utf-8 -*-
"""
Serviço de recálculo de resultados de cartão-resposta (AnswerSheetResult)
após edição de gabarito (AnswerSheetGabarito.correct_answers).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


_VALID_LETTERS = {"A", "B", "C", "D", "E", "F", "G", "H"}


def _normalize_question_map(raw: Any) -> Dict[int, Optional[str]]:
    """
    Normaliza mapas no formato {"1": "A", 2: "b", ...} para {1: "A", 2: "B", ...}.
    Mantém None quando o valor for vazio/nulo.
    """
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            import json

            raw = json.loads(raw)
        except Exception:
            return {}
    if not isinstance(raw, dict):
        return {}

    out: Dict[int, Optional[str]] = {}
    for k, v in raw.items():
        try:
            q = int(k)
        except (ValueError, TypeError):
            continue
        if v is None:
            out[q] = None
            continue
        s = str(v).strip().upper()
        out[q] = s if s else None
    return out


def validate_correct_answers_payload(
    correct_answers: Any, num_questions: int
) -> Tuple[bool, Optional[str], Dict[int, Optional[str]]]:
    """
    Valida payload de correct_answers. Retorna (ok, erro, normalized_dict).
    """
    normalized = _normalize_question_map(correct_answers)
    if not normalized:
        return False, "correct_answers é obrigatório", {}
    if not isinstance(num_questions, int) or num_questions <= 0:
        return False, "num_questions inválido no gabarito", {}

    for q, ans in normalized.items():
        if q < 1 or q > num_questions:
            return False, f"Questão fora do intervalo: {q}. Deve estar entre 1 e {num_questions}.", {}
        if ans is None:
            continue
        if ans not in _VALID_LETTERS:
            return False, f"Alternativa inválida na questão {q}: {ans}", {}

    return True, None, normalized


def calcular_correcao(
    detected_answers: Dict[int, Optional[str]], gabarito: Dict[int, Optional[str]]
) -> Dict[str, Any]:
    total_questions = len(gabarito)
    answered = correct = incorrect = unanswered = 0

    for q_num in range(1, total_questions + 1):
        detected = detected_answers.get(q_num)
        correct_answer = gabarito.get(q_num)
        if not detected:
            unanswered += 1
        elif detected == correct_answer:
            correct += 1
            answered += 1
        else:
            incorrect += 1
            answered += 1

    score_percentage = (correct / total_questions * 100) if total_questions > 0 else 0.0
    return {
        "total_questions": total_questions,
        "answered": answered,
        "correct": correct,
        "incorrect": incorrect,
        "unanswered": unanswered,
        "score_percentage": round(score_percentage, 2),
    }


def recalculate_answer_sheet_result_fields(
    *,
    gabarito_obj: Any,
    detected_answers_raw: Any,
) -> Dict[str, Any]:
    """
    Recalcula campos derivados para AnswerSheetResult, sem depender de imagem/OMR.
    Retorna dict com os campos para persistir no AnswerSheetResult.
    """
    from app.services.cartao_resposta.proficiency_by_subject import (
        calcular_proficiencia_por_disciplina,
    )

    gabarito_dict = _normalize_question_map(getattr(gabarito_obj, "correct_answers", None))
    detected_answers = _normalize_question_map(detected_answers_raw)
    num_questions = int(getattr(gabarito_obj, "num_questions", 0) or 0)

    # Garantir presença de todas as questões 1..num_questions
    if num_questions > 0:
        for q in range(1, num_questions + 1):
            detected_answers.setdefault(q, None)
            gabarito_dict.setdefault(q, None)

    correction = calcular_correcao(detected_answers, gabarito_dict)

    blocks_config = getattr(gabarito_obj, "blocks_config", None) or {}
    grade_name = (getattr(gabarito_obj, "grade_name", None) or getattr(gabarito_obj, "title", None) or "") or ""

    proficiency_by_subject, proficiency, grade, classification, _has_matematica = (
        calcular_proficiencia_por_disciplina(
            blocks_config=blocks_config,
            validated_answers=detected_answers,
            gabarito_dict=gabarito_dict,
            grade_name=grade_name,
        )
    )

    return {
        "detected_answers": detected_answers,
        "correct_answers": correction.get("correct", 0),
        "total_questions": correction.get("total_questions", 0),
        "incorrect_answers": correction.get("incorrect", 0),
        "unanswered_questions": correction.get("unanswered", 0),
        "answered_questions": correction.get("answered", 0),
        "score_percentage": correction.get("score_percentage", 0.0),
        "proficiency_by_subject": proficiency_by_subject,
        "proficiency": proficiency,
        "grade": grade,
        "classification": classification,
    }

