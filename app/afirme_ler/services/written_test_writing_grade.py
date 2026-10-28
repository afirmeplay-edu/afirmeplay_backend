# -*- coding: utf-8 -*-
"""
Nota da avaliação escrita.

As 16 objetivas saem do gabarito, a partir da letra lida no cartão. O ditado e o
bilhete vão para a OpenAI somente quando o cartão trouxe a imagem. Sem cartão,
o professor lança essas três questões na mão.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app import db
from app.afirme_ler.models.reading_written_test import (
    ReadingWrittenTest,
    ReadingWrittenTestCorrection,
    ReadingWrittenTestQuestion,
)
from app.models.question import Question

logger = logging.getLogger(__name__)

PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "correcao_escrita_ditado_bilhete.txt"
)
WORD_NUMBERS = (17, 18)
TEXT_NUMBER = 19
MC_MAX = 16
WORD_MAX = 2
TEXT_MAX = 14
CRITERIA = (
    "adequacao",
    "tipologia",
    "uso_pagina",
    "ortografia",
    "pontuacao",
    "coesao",
    "segmentacao",
)
_CRITERIA_ALIASES = {
    "adequacao": "adequacao",
    "tipologia": "tipologia",
    "uso_pagina": "uso_pagina",
    "usopagina": "uso_pagina",
    "ortografia": "ortografia",
    "pontuacao": "pontuacao",
    "coesao": "coesao",
    "segmentacao": "segmentacao",
}


def _prompt_text() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _model_name() -> str:
    return os.getenv("OPENAI_MODEL") or "gpt-4o"


def _links(written_test_id: str) -> List[Dict[str, Any]]:
    rows = (
        ReadingWrittenTestQuestion.query
        .filter(ReadingWrittenTestQuestion.written_test_id == str(written_test_id))
        .order_by(ReadingWrittenTestQuestion.order.asc())
        .all()
    )
    if not rows:
        return []
    found = {
        question.id: question
        for question in Question.query.filter(
            Question.id.in_([row.question_id for row in rows])
        ).all()
    }
    items = []
    for row in rows:
        question = found.get(row.question_id)
        if question is None:
            continue
        items.append({"number": int(row.order), "question": question})
    return items


def _series_name(written_test_id: str) -> str:
    written_test = db.session.get(ReadingWrittenTest, str(written_test_id))
    if written_test is None:
        return ""
    from app.models.grades import Grade

    names = []
    for raw in written_test.grade_ids or []:
        try:
            grade_id = raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))
        except (TypeError, ValueError):
            continue
        grade = db.session.get(Grade, grade_id)
        if grade is not None and grade.name:
            names.append(str(grade.name))
    return ", ".join(names)


def _id_set(items: List[Dict[str, Any]]) -> set:
    return {str(item.get("questionId")) for item in items if item.get("questionId")}


def score_multiple_choice(
    written_test_id: str,
    answers: Dict[str, Dict[str, Any]],
    blank: List[Dict[str, Any]],
    invalid: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """1 ponto se a letra lida é o gabarito. Em branco ou marca dupla vale 0."""
    blank_ids = _id_set(blank)
    invalid_ids = _id_set(invalid)
    items = []
    for entry in _links(written_test_id):
        number = entry["number"]
        question = entry["question"]
        if number > MC_MAX or question.question_type not in ("multipleChoice", "multiple_choice"):
            continue
        question_id = str(question.id)
        answer_key = str(question.correct_answer or "").strip().upper()
        marked = answers.get(question_id) or {}
        letter = str(marked.get("letter") or "").strip().upper()
        if not answer_key or (
            question_id not in answers and question_id not in blank_ids and question_id not in invalid_ids
        ):
            status, points, shown = "PENDENTE", None, letter or None
        elif question_id in invalid_ids:
            status, points, shown = "INVALIDA", 0, None
        elif question_id in blank_ids or not letter:
            status, points, shown = "EM_BRANCO", 0, None
        elif letter == answer_key:
            status, points, shown = "CORRETA", 1, letter
        else:
            status, points, shown = "INCORRETA", 0, letter
        items.append({
            "number": number,
            "questionId": question_id,
            "letter": shown,
            "answerKey": answer_key or None,
            "points": points,
            "status": status,
        })
    decided = [item["points"] for item in items if item["points"] is not None]
    points = sum(decided) if items and len(decided) == len(items) else None
    return {"items": items, "points": points, "maxPoints": MC_MAX}


def public_objective(stored: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not stored or not stored.get("items"):
        return None
    return {
        "points": stored.get("points"),
        "maxPoints": MC_MAX,
        "items": [
            {
                "number": item.get("number"),
                "questionId": item.get("questionId"),
                "letter": item.get("letter"),
                "answerKey": item.get("answerKey"),
                "points": item.get("points"),
                "status": item.get("status"),
            }
            for item in stored["items"]
        ],
    }


def _writing_question(entry: Dict[str, Any]) -> Optional[str]:
    question = entry["question"]
    if entry["number"] in WORD_NUMBERS and question.question_type == "dictation":
        return "word"
    if entry["number"] == TEXT_NUMBER and question.question_type == "text_production":
        return "text"
    return None


def _images_by_question(pages: List[Dict[str, Any]]) -> Dict[str, bytes]:
    found: Dict[str, bytes] = {}
    for page in pages:
        for question_id, crop in (page.get("crops") or {}).items():
            png = crop.get("png")
            if png:
                found[str(question_id)] = png
    return found


def _optional_int(value: Any, limit: int) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int) or value < 0 or value > limit:
        return None
    return value


def _required_int(value: Any, limit: int, label: str) -> int:
    parsed = _optional_int(value, limit)
    if parsed is None:
        raise ValueError(f"{label} deve ser um inteiro de 0 a {limit}.")
    return parsed


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _confidence(value: Any) -> str:
    text = _text(value).upper().replace("É", "E")
    if text in ("ALTA", "BAIXA"):
        return text
    if text in ("MEDIA", "MÉDIA"):
        return "MÉDIA"
    return "MÉDIA"


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _normalize_word(raw: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    question = entry["question"]
    points = _optional_int(raw.get("pontos", raw.get("points")), WORD_MAX)
    status = _text(raw.get("status")).upper() or ("CORRIGIDA" if points is not None else "PENDENTE")
    if status not in ("CORRIGIDA", "PENDENTE", "NÃO_APLICADA", "NAO_APLICADA", "EM_BRANCO"):
        status = "PENDENTE" if points is None else "CORRIGIDA"
    if status == "NAO_APLICADA":
        status = "NÃO_APLICADA"
    if status != "CORRIGIDA":
        points = 0 if status == "EM_BRANCO" else None
    confidence = _confidence(raw.get("confianca_leitura", raw.get("confidence")))
    needs_review = bool(raw.get("necessita_revisao_humana") or raw.get("needsReview"))
    if points == 1 or confidence == "BAIXA" or status == "PENDENTE":
        needs_review = True
    classification = {2: "CORRETA", 1: "PARCIAL", 0: "INCORRETA"}.get(points, "")
    return {
        "number": entry["number"],
        "questionId": str(question.id),
        "stimulus": "DITADO",
        "expected": _text(question.correct_answer),
        "transcription": _text(raw.get("transcricao_original", raw.get("transcription"))),
        "points": points,
        "classification": classification,
        "justification": _text(raw.get("justificativa", raw.get("justification"))),
        "confidence": confidence,
        "needsReview": needs_review,
        "status": status,
    }


def _criteria_from(raw: Dict[str, Any]) -> Dict[str, Optional[int]]:
    source = raw.get("criterios") or raw.get("criteria") or raw
    if not isinstance(source, dict):
        source = {}
    values: Dict[str, Optional[int]] = {}
    for key, target in _CRITERIA_ALIASES.items():
        if key in source and target not in values:
            values[target] = _optional_int(source.get(key), WORD_MAX)
    for name in CRITERIA:
        values.setdefault(name, _optional_int(raw.get(name), WORD_MAX))
    return {name: values.get(name) for name in CRITERIA}


def _normalize_text(raw: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    question = entry["question"]
    criteria = _criteria_from(raw)
    status = _text(raw.get("status")).upper() or "CORRIGIDA"
    if status == "NAO_APLICADA":
        status = "NÃO_APLICADA"
    if status == "EM_BRANCO":
        criteria = {name: 0 for name in CRITERIA}
    elif status == "PENDENTE" or any(value is None for value in criteria.values()):
        status = "PENDENTE"
    points = sum(criteria.values()) if all(value is not None for value in criteria.values()) else None
    if points is not None and points > TEXT_MAX:
        points = None
        status = "PENDENTE"
    confidence = _confidence(raw.get("confianca_leitura", raw.get("confidence")))
    needs_review = bool(raw.get("necessita_revisao_humana") or raw.get("needsReview"))
    if confidence == "BAIXA" or status == "PENDENTE":
        needs_review = True
    justifications = raw.get("justificativas_por_criterio") or raw.get("justifications") or {}
    if not isinstance(justifications, dict):
        justifications = {}
    return {
        "number": TEXT_NUMBER,
        "questionId": str(question.id),
        "genre": "BILHETE",
        "transcription": _text(raw.get("transcricao_original", raw.get("transcription"))),
        "criteria": criteria,
        "justifications": {name: _text(justifications.get(name)) for name in CRITERIA},
        "points": points,
        "confidence": confidence,
        "needsReview": needs_review,
        "status": status,
        "prompt": _text(question.text),
    }


def _totals(words: List[Dict[str, Any]], production: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    word_points = [item.get("points") for item in words]
    words_total = sum(word_points) if words and all(point is not None for point in word_points) else None
    text_points = production.get("points") if production else None
    needs_review = any(item.get("needsReview") for item in words) or bool(
        production and production.get("needsReview")
    )
    complete = words_total is not None and text_points is not None and not needs_review
    return {
        "wordPoints": words_total,
        "textPoints": text_points,
        "status": "CONCLUIDA" if complete else "PENDENTE_REVISAO",
    }


def _public_word(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "number": item.get("number"),
        "questionId": item.get("questionId"),
        "stimulus": item.get("stimulus"),
        "expected": item.get("expected"),
        "transcription": item.get("transcription"),
        "points": item.get("points"),
        "classification": item.get("classification"),
        "justification": item.get("justification"),
        "confidence": item.get("confidence"),
        "needsReview": bool(item.get("needsReview")),
        "status": item.get("status"),
    }


def _public_production(item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not item:
        return None
    return {
        "number": item.get("number"),
        "questionId": item.get("questionId"),
        "genre": item.get("genre") or "BILHETE",
        "transcription": item.get("transcription"),
        "criteria": item.get("criteria") or {},
        "justifications": item.get("justifications") or {},
        "points": item.get("points"),
        "confidence": item.get("confidence"),
        "needsReview": bool(item.get("needsReview")),
        "status": item.get("status"),
    }


def public_writing(stored: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not stored or not stored.get("source"):
        return None
    return {
        "source": stored.get("source"),
        "status": stored.get("status"),
        "model": stored.get("model"),
        "message": stored.get("message"),
        "words": [_public_word(item) for item in stored.get("words") or []],
        "production": _public_production(stored.get("production")),
        "wordPoints": stored.get("wordPoints"),
        "textPoints": stored.get("textPoints"),
        "feedback": stored.get("feedback") or {},
    }


def _parse_model_json(content: str) -> Dict[str, Any]:
    raw = (content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        fence = raw.rfind("```")
        if fence >= 0:
            raw = raw[:fence]
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("A IA não devolveu um objeto JSON.")
    return data


def _feedback(raw: Dict[str, Any]) -> Dict[str, Any]:
    block = raw.get("devolutiva") or raw.get("feedback") or {}
    if not isinstance(block, dict):
        block = {}
    return {
        "demonstrated": _string_list(block.get("aprendizagens_demonstradas") or block.get("demonstrated")),
        "difficulties": _string_list(block.get("dificuldades_identificadas") or block.get("difficulties")),
        "interventions": _string_list(block.get("intervencoes_recomendadas") or block.get("interventions")),
        "notes": _text(block.get("observacoes_para_professor") or block.get("notes")),
    }


def _apply_model_result(
    previous: Dict[str, Any],
    payload: Dict[str, Any],
    sent: Dict[int, Dict[str, Any]],
    model: str,
) -> Dict[str, Any]:
    by_number = {int(item["number"]): item for item in previous.get("words") or [] if item.get("number")}
    raw_words = payload.get("palavras") or payload.get("words") or []
    if not isinstance(raw_words, list):
        raw_words = []
    returned = {}
    for raw in raw_words:
        if isinstance(raw, dict) and raw.get("numero") is not None:
            returned[int(raw["numero"])] = raw
        elif isinstance(raw, dict) and raw.get("number") is not None:
            returned[int(raw["number"])] = raw
    for number, entry in sent.items():
        if _writing_question(entry) != "word":
            continue
        by_number[number] = _normalize_word(returned.get(number) or {}, entry)
    words = [by_number[number] for number in WORD_NUMBERS if number in by_number]

    production = previous.get("production")
    if TEXT_NUMBER in sent:
        raw_text = payload.get("producao_textual") or payload.get("production") or {}
        if not isinstance(raw_text, dict):
            raw_text = {}
        production = _normalize_text(raw_text, sent[TEXT_NUMBER])

    totals = _totals(words, production)
    return {
        "source": "ia",
        "status": totals["status"],
        "model": model,
        "message": None,
        "words": words,
        "production": production,
        "wordPoints": totals["wordPoints"],
        "textPoints": totals["textPoints"],
        "feedback": _feedback(payload),
    }


def _user_content(
    written_test_id: str,
    student_id: str,
    series: str,
    sent: Dict[int, Dict[str, Any]],
    images: Dict[int, bytes],
) -> List[Dict[str, Any]]:
    lines = [
        f"avaliacao_id: {written_test_id}",
        f"estudante_id: {student_id}",
        f"serie: {series or 'não informada'}",
        "Corrija somente as questões que têm imagem anexada.",
        "Questão sem imagem nesta chamada não recebe nota.",
    ]
    for number in (*WORD_NUMBERS, TEXT_NUMBER):
        entry = sent.get(number)
        if entry is None:
            continue
        question = entry["question"]
        if _writing_question(entry) == "word":
            lines.append(
                f"Questão {number}. tipo_estimulo: DITADO. "
                f"palavra_esperada: {_text(question.correct_answer) or 'AUSENTE'}."
            )
        else:
            lines.append(f"Questão {number}. genero: BILHETE. enunciado: {_text(question.text) or 'AUSENTE'}.")
        if number not in images:
            lines.append(f"Questão {number} está sem imagem.")
    content: List[Dict[str, Any]] = [{"type": "text", "text": "\n".join(lines)}]
    for number in (*WORD_NUMBERS, TEXT_NUMBER):
        png = images.get(number)
        if not png:
            continue
        encoded = base64.b64encode(png).decode("ascii")
        content.append({"type": "text", "text": f"Imagem da questão {number}."})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{encoded}"},
        })
    return content


def _ask_openai(content: List[Dict[str, Any]]) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=90)
    model = _model_name()
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _prompt_text()},
            {"role": "user", "content": content},
        ],
    )
    message = response.choices[0].message.content or ""
    return _parse_model_json(message)


def _correction_row(written_test_id: str, student_id: str) -> ReadingWrittenTestCorrection:
    row = ReadingWrittenTestCorrection.query.filter_by(
        written_test_id=str(written_test_id), student_id=str(student_id),
    ).first()
    if row is None:
        row = ReadingWrittenTestCorrection(
            written_test_id=str(written_test_id),
            student_id=str(student_id),
        )
        db.session.add(row)
    return row


def grade_scanned_writing(
    written_test_id: str,
    student_id: str,
    pages: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Corrige ditado e bilhete com a imagem do cartão. Sem imagem, não chama a IA."""
    available = _images_by_question(pages)
    sent: Dict[int, Dict[str, Any]] = {}
    images: Dict[int, bytes] = {}
    for entry in _links(written_test_id):
        kind = _writing_question(entry)
        if kind is None:
            continue
        png = available.get(str(entry["question"].id))
        if not png:
            continue
        sent[entry["number"]] = entry
        images[entry["number"]] = png
    if not images:
        return None

    row = _correction_row(written_test_id, student_id)
    previous = dict(row.writing or {})
    model = _model_name()
    try:
        payload = _ask_openai(_user_content(
            written_test_id, student_id, _series_name(written_test_id), sent, images,
        ))
        stored = _apply_model_result(previous, payload, sent, model)
    except Exception:
        logger.exception(
            "Falha na correção da escrita por IA test=%s student=%s", written_test_id, student_id,
        )
        stored = dict(previous)
        stored.update({
            "source": "ia",
            "status": "ERRO",
            "model": model,
            "message": "A correção da escrita não foi concluída.",
        })
    row.writing = stored
    db.session.commit()
    return public_writing(stored)


def _manual_words(payload: Dict[str, Any], entries: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    raw_items = payload.get("words")
    if raw_items is None:
        raw_items = payload.get("palavras")
    if not isinstance(raw_items, list):
        raise ValueError("Informe a transcrição e a nota das questões 17 e 18.")
    by_number = {}
    for item in raw_items:
        if isinstance(item, dict) and item.get("number") is not None:
            by_number[int(item["number"])] = item
        elif isinstance(item, dict) and item.get("numero") is not None:
            by_number[int(item["numero"])] = item
    words = []
    for number in WORD_NUMBERS:
        entry = entries.get(number)
        raw = by_number.get(number)
        if entry is None or raw is None:
            raise ValueError("Informe a transcrição e a nota das questões 17 e 18.")
        points = _required_int(raw.get("points", raw.get("pontos")), WORD_MAX, f"A questão {number}")
        words.append({
            "number": number,
            "questionId": str(entry["question"].id),
            "stimulus": "DITADO",
            "expected": _text(entry["question"].correct_answer),
            "transcription": _text(raw.get("transcription", raw.get("transcricao"))),
            "points": points,
            "classification": {2: "CORRETA", 1: "PARCIAL", 0: "INCORRETA"}[points],
            "justification": _text(raw.get("justification", raw.get("justificativa"))),
            "confidence": "ALTA",
            "needsReview": False,
            "status": "CORRIGIDA",
        })
    return words


def _manual_production(payload: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    raw = payload.get("production")
    if raw is None:
        raw = payload.get("producaoTextual") or payload.get("producao_textual")
    if not isinstance(raw, dict):
        raise ValueError("Informe a transcrição e os sete critérios do bilhete.")
    criteria = {}
    aliases = {
        "adequacao": "adequacao",
        "tipologia": "tipologia",
        "usoPagina": "uso_pagina",
        "uso_pagina": "uso_pagina",
        "ortografia": "ortografia",
        "pontuacao": "pontuacao",
        "coesao": "coesao",
        "segmentacao": "segmentacao",
    }
    source = raw.get("criteria") if isinstance(raw.get("criteria"), dict) else raw
    translated = {}
    for key, target in aliases.items():
        if key in source:
            translated[target] = source[key]
    for name in CRITERIA:
        label = "uso da página" if name == "uso_pagina" else name
        criteria[name] = _required_int(translated.get(name), WORD_MAX, f"O critério {label} do bilhete")
    return {
        "number": TEXT_NUMBER,
        "questionId": str(entry["question"].id),
        "genre": "BILHETE",
        "transcription": _text(raw.get("transcription", raw.get("transcricao"))),
        "criteria": criteria,
        "justifications": {},
        "points": sum(criteria.values()),
        "confidence": "ALTA",
        "needsReview": False,
        "status": "CORRIGIDA",
        "prompt": _text(entry["question"].text),
    }


def save_manual_writing(written_test_id: str, student_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Lançamento do professor para o ditado e o bilhete. Não altera a nota das objetivas."""
    from app.models.student import Student
    from app.socioeconomic_forms.services.answer_sheet_correction import student_display_name

    if not isinstance(payload, dict):
        raise ValueError("Corpo da requisição inválido.")
    student = db.session.get(Student, str(student_id))
    if student is None:
        raise LookupError("Aluno não encontrado.")
    if db.session.get(ReadingWrittenTest, str(written_test_id)) is None:
        raise LookupError("Avaliação escrita não encontrada.")

    entries = {entry["number"]: entry for entry in _links(written_test_id)}
    words = _manual_words(payload, entries)
    production_entry = entries.get(TEXT_NUMBER)
    if production_entry is None or _writing_question(production_entry) != "text":
        raise ValueError("A avaliação não tem o bilhete na questão 19.")
    production = _manual_production(payload, production_entry)
    totals = _totals(words, production)
    stored = {
        "source": "manual",
        "status": "CONCLUIDA",
        "model": None,
        "message": None,
        "words": words,
        "production": production,
        "wordPoints": totals["wordPoints"],
        "textPoints": totals["textPoints"],
        "feedback": {},
    }
    row = _correction_row(written_test_id, student_id)
    row.writing = stored
    db.session.commit()
    return {
        "correctionId": row.id,
        "studentId": str(student.id),
        "studentName": student_display_name(student),
        "objective": public_objective(row.objective),
        "writing": public_writing(stored),
    }


def list_corrections(written_test_id: str) -> Dict[str, Any]:
    from app.models.student import Student
    from app.socioeconomic_forms.services.answer_sheet_correction import student_display_name
    from app.afirme_ler.services.written_test_answer_sheet_correction import (
        _public_answers,
        _public_crops,
    )

    if db.session.get(ReadingWrittenTest, str(written_test_id)) is None:
        raise LookupError("Avaliação escrita não encontrada.")
    rows = (
        ReadingWrittenTestCorrection.query
        .filter(ReadingWrittenTestCorrection.written_test_id == str(written_test_id))
        .all()
    )
    students = []
    for row in rows:
        student = db.session.get(Student, row.student_id)
        students.append({
            "correctionId": row.id,
            "studentId": row.student_id,
            "studentName": student_display_name(student) if student else None,
            "answers": _public_answers(row.answers or {}),
            "blank": list(row.blank or []),
            "invalid": list(row.invalid or []),
            "crops": _public_crops(row.crops or {}),
            "pages": list(row.pages or []),
            "objective": public_objective(row.objective),
            "writing": public_writing(row.writing),
        })
    students.sort(key=lambda item: (item["studentName"] or "", item["studentId"] or ""))
    return {"writtenTestId": str(written_test_id), "students": students}
