# -*- coding: utf-8 -*-
"""
Nota da avaliação escrita.

As 16 objetivas saem do gabarito, a partir da letra lida no cartão. O ditado e o
bilhete vão para a OpenAI somente quando o cartão trouxe a imagem. Sem cartão,
o professor lança essas três questões na mão.

A escrita passa por duas leituras independentes, na mesma conta da OpenAI e com
modelos diferentes (OPENAI_MODEL e OPENAI_MODEL_RELEITURA). Nenhuma das duas
recebe a palavra esperada. Se elas concordam, uma terceira chamada avalia a
transcrição conferida. Divergência fica para o professor, sem nota inventada.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone
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

_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
PROMPT_PATH = _PROMPTS / "correcao_escrita_ditado_bilhete.txt"
READING_PROMPT_PATH = _PROMPTS / "transcricao_escrita.txt"
READING_TASK = "TAREFA: TRANSCRICAO_LITERAL"
EVALUATION_TASK = "TAREFA: AVALIACAO_PEDAGOGICA"
READING_PROMPT_VERSION = "transcricao-escrita-1"
EVALUATION_PROMPT_VERSION = "avaliacao-escrita-1"
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


def _reading_prompt() -> str:
    return f"{READING_TASK}\n\n{READING_PROMPT_PATH.read_text(encoding='utf-8')}"


def _evaluation_prompt() -> str:
    return f"{EVALUATION_TASK}\n\n{_prompt_text()}"


def _model_name() -> str:
    return os.getenv("OPENAI_MODEL") or "gpt-4o"


def _reread_model() -> str:
    configured = os.getenv("OPENAI_MODEL_RELEITURA") or "gpt-4o-mini"
    if configured == _model_name():
        logger.warning(
            "OPENAI_MODEL e OPENAI_MODEL_RELEITURA são o mesmo modelo (%s).",
            configured,
        )
    return configured


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


def _stimulus(question: Any) -> str:
    if getattr(question, "question_type", None) != "dictation":
        return "word"
    value = getattr(question, "writing_stimulus", None) or "word"
    return value if value in ("word", "image") else "word"


def _stimulus_label(question: Any) -> str:
    return "IMAGEM" if _stimulus(question) == "image" else "DITADO"


def _reference(question: Any) -> str:
    if _stimulus(question) == "image":
        return _text(getattr(question, "writing_reference", None))
    return _text(getattr(question, "correct_answer", None))


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
        "stimulus": _stimulus_label(question),
        "expected": _reference(question),
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


def _public_readings(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    readings = []
    for reading in item.get("readings") or []:
        if not isinstance(reading, dict):
            continue
        readings.append({
            "model": reading.get("model"),
            "transcription": reading.get("transcription") or "",
            "situation": reading.get("situation"),
            "uncertain": list(reading.get("uncertain") or []),
        })
    return readings


def _public_word(item: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
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
    readings = _public_readings(item)
    if readings:
        payload["readings"] = readings
        payload["secondTranscription"] = item.get("secondTranscription") or ""
    return payload


def _public_production(item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not item:
        return None
    payload = {
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
    readings = _public_readings(item)
    if readings:
        payload["readings"] = readings
        payload["secondTranscription"] = item.get("secondTranscription") or ""
    return payload


def public_writing(stored: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not stored or not stored.get("source"):
        return None
    payload = {
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
    if stored.get("models"):
        payload["models"] = stored["models"]
    if "published" in stored:
        payload["published"] = bool(stored.get("published"))
    elif stored.get("source") == "manual":
        payload["published"] = True
    else:
        payload["published"] = False
    if stored.get("review"):
        payload["review"] = stored["review"]
    if stored.get("audit"):
        payload["audit"] = stored["audit"]
    if stored.get("promptVersions"):
        payload["promptVersions"] = stored["promptVersions"]
    return payload


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


def _fold_word(text: str) -> str:
    return " ".join(text.casefold().split())


def _fold_text(text: str) -> str:
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        folded = " ".join(line.casefold().split())
        if folded:
            lines.append(folded)
    return "\n".join(lines)


def _situation(value: Any) -> str:
    text = _text(value).lower().replace("í", "i").replace("é", "e").replace(" ", "_")
    if text in ("legivel", "duvidosa", "ilegivel", "em_branco"):
        return text
    return "duvidosa"


def _parse_reading_items(payload: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    raw_items = payload.get("questoes") or payload.get("items") or []
    if not isinstance(raw_items, list):
        raw_items = []
    found: Dict[int, Dict[str, Any]] = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        number = raw.get("numero", raw.get("number"))
        try:
            number = int(number)
        except (TypeError, ValueError):
            continue
        uncertain = raw.get("trechos_duvidosos", raw.get("uncertain")) or []
        if not isinstance(uncertain, list):
            uncertain = []
        found[number] = {
            "transcription": _text(raw.get("transcricao_literal", raw.get("transcription"))),
            "situation": _situation(raw.get("situacao", raw.get("situation"))),
            "uncertain": [str(item).strip() for item in uncertain if str(item or "").strip()],
        }
    return found


def _reading_of(parsed: Dict[int, Dict[str, Any]], number: int, model: str) -> Dict[str, Any]:
    item = parsed.get(number) or {
        "transcription": "",
        "situation": "duvidosa",
        "uncertain": [],
    }
    return {**item, "model": model}


def readings_agree(first: Dict[str, Any], second: Dict[str, Any], kind: str) -> bool:
    """Duas leituras concordam quando a situação e o texto literal batem."""
    if first.get("situation") != second.get("situation"):
        return False
    if first.get("uncertain") or second.get("uncertain"):
        return False
    if first.get("situation") == "em_branco":
        return True
    if first.get("situation") != "legivel":
        return False
    fold = _fold_text if kind == "text" else _fold_word
    left = fold(_text(first.get("transcription")))
    right = fold(_text(second.get("transcription")))
    return bool(left) and left == right


def _review_reason(first: Dict[str, Any], second: Dict[str, Any]) -> str:
    if first.get("situation") != second.get("situation"):
        return "As duas leituras discordaram sobre a situação da resposta."
    if first.get("uncertain") or second.get("uncertain"):
        return "Há trecho duvidoso na leitura."
    if first.get("situation") != "legivel":
        return "A leitura não ficou legível."
    return "As duas leituras divergiram."


def _public_reading(reading: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "model": reading.get("model"),
        "transcription": reading.get("transcription") or "",
        "situation": reading.get("situation"),
        "uncertain": list(reading.get("uncertain") or []),
    }


def _with_readings(item: Dict[str, Any], first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    item["transcription"] = first.get("transcription") or ""
    item["secondTranscription"] = second.get("transcription") or ""
    item["readings"] = [_public_reading(first), _public_reading(second)]
    return item


def _review_word(
    entry: Dict[str, Any],
    first: Dict[str, Any],
    second: Dict[str, Any],
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    question = entry["question"]
    return _with_readings({
        "number": entry["number"],
        "questionId": str(question.id),
        "stimulus": _stimulus_label(question),
        "expected": _reference(question),
        "points": None,
        "classification": "",
        "justification": reason or _review_reason(first, second),
        "confidence": "BAIXA",
        "needsReview": True,
        "status": "PENDENTE",
    }, first, second)


def _blank_word(entry: Dict[str, Any], first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    question = entry["question"]
    return _with_readings({
        "number": entry["number"],
        "questionId": str(question.id),
        "stimulus": _stimulus_label(question),
        "expected": _reference(question),
        "points": 0,
        "classification": "INCORRETA",
        "justification": "Resposta em branco.",
        "confidence": "ALTA",
        "needsReview": False,
        "status": "EM_BRANCO",
    }, first, second)


def _review_text(entry: Dict[str, Any], first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    question = entry["question"]
    return _with_readings({
        "number": TEXT_NUMBER,
        "questionId": str(question.id),
        "genre": "BILHETE",
        "criteria": {name: None for name in CRITERIA},
        "justifications": {name: "" for name in CRITERIA},
        "points": None,
        "confidence": "BAIXA",
        "needsReview": True,
        "status": "PENDENTE",
        "prompt": _text(question.text),
    }, first, second)


def _blank_text(entry: Dict[str, Any], first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    question = entry["question"]
    return _with_readings({
        "number": TEXT_NUMBER,
        "questionId": str(question.id),
        "genre": "BILHETE",
        "criteria": {name: 0 for name in CRITERIA},
        "justifications": {name: "Resposta em branco." for name in CRITERIA},
        "points": 0,
        "confidence": "ALTA",
        "needsReview": False,
        "status": "EM_BRANCO",
        "prompt": _text(question.text),
    }, first, second)


def _image_parts(images: Dict[int, bytes], numbers: List[int]) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = []
    for number in numbers:
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


def _reading_content(
    written_test_id: str,
    series: str,
    sent: Dict[int, Dict[str, Any]],
    images: Dict[int, bytes],
) -> List[Dict[str, Any]]:
    lines = [
        f"avaliacao_id: {written_test_id}",
        f"serie: {series or 'não informada'}",
        "Transcreva somente as questões com imagem anexada.",
        "Não avalie e não atribua nota.",
    ]
    numbers = []
    for number in (*WORD_NUMBERS, TEXT_NUMBER):
        entry = sent.get(number)
        if entry is None or number not in images:
            continue
        numbers.append(number)
        if _writing_question(entry) == "word":
            lines.append(f"Questão {number}. Área de uma palavra.")
        else:
            lines.append(f"Questão {number}. Área de produção de texto. Preserve as quebras de linha.")
    return [{"type": "text", "text": "\n".join(lines)}, *_image_parts(images, numbers)]


def _evaluation_content(
    written_test_id: str,
    series: str,
    sent: Dict[int, Dict[str, Any]],
    images: Dict[int, bytes],
    agreed: Dict[int, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    lines = [
        f"avaliacao_id: {written_test_id}",
        f"serie: {series or 'não informada'}",
        "A transcrição abaixo já foi conferida. Não a substitua.",
        "Avalie somente as questões desta chamada.",
    ]
    image_numbers = []
    for number in (*WORD_NUMBERS, TEXT_NUMBER):
        entry = sent.get(number)
        reading = agreed.get(number)
        if entry is None or reading is None:
            continue
        question = entry["question"]
        transcription = reading.get("transcription") or ""
        if _writing_question(entry) == "word":
            if _stimulus(question) == "image":
                lines.append(
                    f"Questão {number}. tipo_estimulo: IMAGEM. "
                    f"descricao_da_imagem: {_reference(question) or 'AUSENTE'}. "
                    f"transcricao_conferida: {transcription}."
                )
            else:
                lines.append(
                    f"Questão {number}. tipo_estimulo: DITADO. "
                    f"palavra_esperada: {_reference(question) or 'AUSENTE'}. "
                    f"transcricao_conferida: {transcription}."
                )
        else:
            lines.append(
                f"Questão {number}. genero: BILHETE. "
                f"enunciado: {_text(question.text) or 'AUSENTE'}. "
                f"transcricao_conferida: {transcription}."
            )
            image_numbers.append(number)
    return [{"type": "text", "text": "\n".join(lines)}, *_image_parts(images, image_numbers)]


def _ask_openai(client: Any, model: str, system: str, content: List[Dict[str, Any]]) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
    )
    message = response.choices[0].message.content or ""
    return _parse_model_json(message)


def _openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")
    from openai import OpenAI

    return OpenAI(api_key=api_key, timeout=90)


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


def _pair_readings(
    sent: Dict[int, Dict[str, Any]],
    first_parsed: Dict[int, Dict[str, Any]],
    second_parsed: Dict[int, Dict[str, Any]],
    first_model: str,
    second_model: str,
) -> Dict[int, Dict[str, Any]]:
    paired = {}
    for number, entry in sent.items():
        kind = _writing_question(entry)
        first = _reading_of(first_parsed, number, first_model)
        second = _reading_of(second_parsed, number, second_model)
        if readings_agree(first, second, kind or "word"):
            decision = "blank" if first["situation"] == "em_branco" else "score"
        else:
            decision = "review"
        reason = None
        question = entry["question"]
        if (
            decision == "score"
            and kind == "word"
            and _stimulus(question) == "image"
            and not _reference(question)
        ):
            decision = "review"
            reason = "A figura não tem descrição. Gere a descrição da imagem na questão."
        paired[number] = {
            "first": first,
            "second": second,
            "decision": decision,
            "kind": kind,
            "reason": reason,
        }
    return paired


def _assemble_writing(
    previous: Dict[str, Any],
    sent: Dict[int, Dict[str, Any]],
    paired: Dict[int, Dict[str, Any]],
    payload: Optional[Dict[str, Any]],
    models: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    score_sent = {
        number: sent[number]
        for number, item in paired.items()
        if item["decision"] == "score"
    }
    scored = (
        _apply_model_result({}, payload or {}, score_sent, models.get("avaliacao") or "")
        if payload is not None
        else {"words": [], "production": None, "feedback": {}}
    )
    scored_words = {item["number"]: item for item in scored.get("words") or []}
    previous_words = {
        int(item["number"]): item
        for item in previous.get("words") or []
        if item.get("number")
    }

    words = []
    for number in WORD_NUMBERS:
        if number not in sent:
            if number in previous_words:
                words.append(previous_words[number])
            continue
        pair = paired[number]
        first, second = pair["first"], pair["second"]
        if pair["decision"] == "review":
            words.append(_review_word(sent[number], first, second, pair.get("reason")))
        elif pair["decision"] == "blank":
            words.append(_blank_word(sent[number], first, second))
        elif number in scored_words:
            words.append(_with_readings(scored_words[number], first, second))
        else:
            pending = _review_word(sent[number], first, second)
            pending["justification"] = "A avaliação pedagógica não devolveu esta questão."
            words.append(pending)

    production = previous.get("production")
    if TEXT_NUMBER in sent:
        pair = paired[TEXT_NUMBER]
        first, second = pair["first"], pair["second"]
        if pair["decision"] == "review":
            production = _review_text(sent[TEXT_NUMBER], first, second)
        elif pair["decision"] == "blank":
            production = _blank_text(sent[TEXT_NUMBER], first, second)
        elif scored.get("production"):
            production = _with_readings(scored["production"], first, second)
        else:
            production = _review_text(sent[TEXT_NUMBER], first, second)
            production["justification"] = "A avaliação pedagógica não devolveu o bilhete."

    totals = _totals(words, production)
    return {
        "source": "ia",
        "status": totals["status"],
        "model": models.get("avaliacao") or models.get("leitura"),
        "models": models,
        "message": None,
        "words": words,
        "production": production,
        "wordPoints": totals["wordPoints"],
        "textPoints": totals["textPoints"],
        "feedback": scored.get("feedback") or {},
    }


def grade_scanned_writing(
    written_test_id: str,
    student_id: str,
    pages: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Lê o ditado e o bilhete duas vezes e só então avalia o que coincidiu."""
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
    primary = _model_name()
    second_model = _reread_model()
    models = {"leitura": primary, "releitura": second_model, "avaliacao": None}
    try:
        client = _openai_client()
        series = _series_name(written_test_id)
        reading_content = _reading_content(written_test_id, series, sent, images)
        system = _reading_prompt()
        first_payload = _ask_openai(client, primary, system, reading_content)
        second_payload = _ask_openai(client, second_model, system, reading_content)
        paired = _pair_readings(
            sent, _parse_reading_items(first_payload), _parse_reading_items(second_payload),
            primary, second_model,
        )
    except Exception:
        logger.exception(
            "Falha na leitura da escrita por IA test=%s student=%s", written_test_id, student_id,
        )
        stored = dict(previous)
        stored.update({
            "source": "ia",
            "status": "ERRO",
            "model": primary,
            "models": models,
            "message": "A correção da escrita não foi concluída.",
        })
        row.writing = stored
        db.session.commit()
        return public_writing(stored)

    agreed = {
        number: item["first"]
        for number, item in paired.items()
        if item["decision"] == "score"
    }
    payload = None
    evaluation_failed = False
    if agreed:
        models["avaliacao"] = primary
        try:
            payload = _ask_openai(
                client,
                primary,
                _evaluation_prompt(),
                _evaluation_content(written_test_id, series, sent, images, agreed),
            )
        except Exception:
            logger.exception(
                "Falha na avaliação da escrita por IA test=%s student=%s",
                written_test_id,
                student_id,
            )
            evaluation_failed = True
    stored = _assemble_writing(previous, sent, paired, payload, models)
    if evaluation_failed:
        stored["status"] = "ERRO"
        stored["message"] = "A avaliação pedagógica não foi concluída."
    stored["published"] = False
    stored["promptVersions"] = {
        "leitura": READING_PROMPT_VERSION,
        "avaliacao": EVALUATION_PROMPT_VERSION if models.get("avaliacao") else None,
    }
    stored["audit"] = _append_audit(previous.get("audit"), _audit_entry(
        "leitura",
        None,
        stored,
        decision=None,
    ))
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
            "stimulus": _stimulus_label(entry["question"]),
            "expected": _reference(entry["question"]),
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _audit_items(stored: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    for word in stored.get("words") or []:
        items.append({
            "number": word.get("number"),
            "transcription": word.get("transcription") or "",
            "points": word.get("points"),
            "status": word.get("status"),
            "evidence": word.get("justification") or "",
        })
    production = stored.get("production") or {}
    if production:
        items.append({
            "number": TEXT_NUMBER,
            "transcription": production.get("transcription") or "",
            "points": production.get("points"),
            "status": production.get("status"),
            "evidence": production.get("justifications") or {},
        })
    return items


def _audit_entry(
    action: str,
    actor_id: Optional[str],
    stored: Dict[str, Any],
    decision: Optional[str],
) -> Dict[str, Any]:
    return {
        "at": _now_iso(),
        "action": action,
        "actorId": actor_id,
        "decision": decision,
        "promptVersions": stored.get("promptVersions"),
        "models": stored.get("models"),
        "items": _audit_items(stored),
    }


def _append_audit(previous: Any, entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    audit = list(previous) if isinstance(previous, list) else []
    audit.append(entry)
    return audit


def _ready_to_release(stored: Dict[str, Any]) -> bool:
    if not stored or stored.get("status") == "ERRO" or stored.get("source") not in ("ia", "manual"):
        return False
    words = stored.get("words") or []
    production = stored.get("production")
    if len(words) < len(WORD_NUMBERS) or not production:
        return False
    for item in (*words, production):
        if item.get("points") is None or item.get("status") in ("PENDENTE", "NÃO_APLICADA"):
            return False
    return True


def _student_result(row: ReadingWrittenTestCorrection, student: Any) -> Dict[str, Any]:
    from app.socioeconomic_forms.services.answer_sheet_correction import student_display_name

    return {
        "correctionId": row.id,
        "studentId": str(student.id),
        "studentName": student_display_name(student),
        "objective": public_objective(row.objective),
        "writing": public_writing(row.writing),
    }


def _confirmed_numbers(payload: Dict[str, Any]) -> Dict[int, str]:
    found: Dict[int, str] = {}
    raw_items = payload.get("words")
    if raw_items is None:
        raw_items = payload.get("palavras")
    if raw_items is not None:
        if not isinstance(raw_items, list):
            raise ValueError("words deve ser uma lista de {number, transcription}.")
        for item in raw_items:
            if not isinstance(item, dict) or item.get("number") is None and item.get("numero") is None:
                raise ValueError("Cada palavra conferida precisa de number e transcription.")
            number = int(item.get("number", item.get("numero")))
            if number not in WORD_NUMBERS:
                raise ValueError("A conferência de palavra aceita as questões 17 e 18.")
            found[number] = _text(item.get("transcription", item.get("transcricao")))
    raw_text = payload.get("production")
    if raw_text is None:
        raw_text = payload.get("producaoTextual") or payload.get("producao_textual")
    if raw_text is not None:
        if not isinstance(raw_text, dict):
            raise ValueError("production deve trazer a transcription conferida.")
        found[TEXT_NUMBER] = _text(raw_text.get("transcription", raw_text.get("transcricao")))
    if not found:
        raise ValueError("Informe a transcrição conferida de ao menos uma questão.")
    return found


def confirm_writing(
    written_test_id: str,
    student_id: str,
    payload: Dict[str, Any],
    reviewer_id: str,
) -> Dict[str, Any]:
    """Troca a transcrição pendente pela do professor e avalia de novo só esse texto."""
    from app.models.student import Student

    if not isinstance(payload, dict):
        raise ValueError("Corpo da requisição inválido.")
    student = db.session.get(Student, str(student_id))
    if student is None:
        raise LookupError("Aluno não encontrado.")
    if db.session.get(ReadingWrittenTest, str(written_test_id)) is None:
        raise LookupError("Avaliação escrita não encontrada.")
    row = ReadingWrittenTestCorrection.query.filter_by(
        written_test_id=str(written_test_id), student_id=str(student_id),
    ).first()
    if row is None or not (row.writing or {}).get("words"):
        raise ValueError("Não há leitura do cartão para conferir.")
    if (row.writing or {}).get("source") != "ia":
        raise ValueError("O lançamento manual não usa conferência de transcrição.")

    confirmed = _confirmed_numbers(payload)
    entries = {entry["number"]: entry for entry in _links(written_test_id)}
    stored = dict(row.writing or {})
    words = [dict(item) for item in stored.get("words") or []]
    by_number = {int(item["number"]): item for item in words if item.get("number")}
    production = dict(stored.get("production") or {})
    agreed: Dict[int, Dict[str, Any]] = {}
    sent: Dict[int, Dict[str, Any]] = {}

    for number, transcription in confirmed.items():
        entry = entries.get(number)
        if entry is None:
            raise ValueError(f"A avaliação não tem a questão {number}.")
        if not transcription:
            if number == TEXT_NUMBER:
                production = _blank_text(entry, {"transcription": "", "model": "professor", "situation": "em_branco", "uncertain": []}, {"transcription": "", "model": "professor", "situation": "em_branco", "uncertain": []})
            else:
                blank = _blank_word(entry, {"transcription": "", "model": "professor", "situation": "em_branco", "uncertain": []}, {"transcription": "", "model": "professor", "situation": "em_branco", "uncertain": []})
                previous = by_number.get(number) or {}
                if previous.get("readings"):
                    blank["readings"] = previous["readings"]
                by_number[number] = blank
            continue
        agreed[number] = {"transcription": transcription, "situation": "legivel", "uncertain": []}
        sent[number] = entry

    payload_model = None
    if agreed:
        client = _openai_client()
        primary = _model_name()
        images = _confirmed_images(row, sent)
        payload_model = _ask_openai(
            client,
            primary,
            _evaluation_prompt(),
            _evaluation_content(written_test_id, _series_name(written_test_id), sent, images, agreed),
        )
        scored = _apply_model_result({}, payload_model, sent, primary)
        for item in scored.get("words") or []:
            number = int(item["number"])
            previous = by_number.get(number) or {}
            item["transcription"] = agreed[number]["transcription"]
            if previous.get("readings"):
                item["readings"] = previous["readings"]
                item["secondTranscription"] = previous.get("secondTranscription") or ""
            by_number[number] = item
        if TEXT_NUMBER in agreed and scored.get("production"):
            production = scored["production"]
            production["transcription"] = agreed[TEXT_NUMBER]["transcription"]
            previous_production = stored.get("production") or {}
            if previous_production.get("readings"):
                production["readings"] = previous_production["readings"]
                production["secondTranscription"] = previous_production.get("secondTranscription") or ""

    words_out = [by_number[number] for number in WORD_NUMBERS if number in by_number]
    totals = _totals(words_out, production)
    models = dict(stored.get("models") or {})
    models["avaliacao"] = models.get("avaliacao") or _model_name()
    stored.update({
        "status": totals["status"],
        "words": words_out,
        "production": production,
        "wordPoints": totals["wordPoints"],
        "textPoints": totals["textPoints"],
        "published": False,
        "review": None,
        "models": models,
        "promptVersions": {
            "leitura": READING_PROMPT_VERSION,
            "avaliacao": EVALUATION_PROMPT_VERSION,
        },
    })
    if payload_model:
        stored["feedback"] = _feedback(payload_model)
    stored["audit"] = _append_audit(stored.get("audit"), _audit_entry(
        "revisao", reviewer_id, stored, decision="transcricao_conferida",
    ))
    row.writing = stored
    db.session.commit()
    return _student_result(row, student)


def _confirmed_images(
    row: ReadingWrittenTestCorrection,
    sent: Dict[int, Dict[str, Any]],
) -> Dict[int, bytes]:
    images: Dict[int, bytes] = {}
    entry = sent.get(TEXT_NUMBER)
    if entry is None:
        return images
    crop = (row.crops or {}).get(str(entry["question"].id)) or {}
    bucket = crop.get("bucket")
    object_name = crop.get("objectName")
    if not bucket or not object_name:
        return images
    try:
        from app.services.storage.minio_service import MinIOService

        png = MinIOService().download_file(bucket, object_name)
    except Exception:
        logger.exception("Falha ao ler o recorte do bilhete para a revisão.")
        return images
    if png:
        images[TEXT_NUMBER] = png
    return images


def release_writing(written_test_id: str, student_id: str, reviewer_id: str) -> Dict[str, Any]:
    """Libera a nota do ditado e do bilhete depois que não há item pendente."""
    from app.models.student import Student

    student = db.session.get(Student, str(student_id))
    if student is None:
        raise LookupError("Aluno não encontrado.")
    if db.session.get(ReadingWrittenTest, str(written_test_id)) is None:
        raise LookupError("Avaliação escrita não encontrada.")
    row = ReadingWrittenTestCorrection.query.filter_by(
        written_test_id=str(written_test_id), student_id=str(student_id),
    ).first()
    stored = dict(row.writing or {}) if row is not None else {}
    if not _ready_to_release(stored):
        raise ValueError(
            "A correção ainda tem questão pendente. Confira a transcrição antes de liberar."
        )
    stored["published"] = True
    stored["status"] = "CONCLUIDA"
    stored["review"] = {
        "reviewerId": reviewer_id,
        "reviewedAt": _now_iso(),
        "decision": "liberada",
    }
    stored["audit"] = _append_audit(stored.get("audit"), _audit_entry(
        "liberacao", reviewer_id, stored, decision="liberada",
    ))
    row.writing = stored
    db.session.commit()
    return _student_result(row, student)


def save_manual_writing(written_test_id: str, student_id: str, payload: Dict[str, Any], reviewer_id: Optional[str] = None) -> Dict[str, Any]:
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
        "published": True,
        "review": {
            "reviewerId": reviewer_id,
            "reviewedAt": _now_iso(),
            "decision": "lancamento_manual",
        },
    }
    stored["audit"] = [_audit_entry("lancamento_manual", reviewer_id, stored, "lancamento_manual")]
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
            "crops": _public_crops(row.crops or {}, written_test_id, row.student_id),
            "pages": list(row.pages or []),
            "objective": public_objective(row.objective),
            "writing": public_writing(row.writing),
        })
    students.sort(key=lambda item: (item["studentName"] or "", item["studentId"] or ""))
    return {"writtenTestId": str(written_test_id), "students": students}
