# -*- coding: utf-8 -*-
"""
Leitura OMR do cartão socioeconômico.

Usa a detecção da prova física (quadrados, alinhamento A4, varredura do QR
e a decisão de tinta V2) chamando esses métodos. Não chama
corrigir_cartao_resposta e não altera esse leitor.

A letra impressa vira o texto da opção na ordem do formulário. Bolha vazia,
dupla marca ou margem pequena não grava a chave. Uma página não apaga a
resposta que a outra página já tinha.
"""

import importlib.util
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from app.services.cartao_resposta.correction_new_grid import AnswerSheetCorrectionNewGrid

logger = logging.getLogger(__name__)

_PDF_RASTER_DPI = 200


def _map_module():
    qualified = "app.socioeconomic_forms.services.answer_sheet_map"
    loaded = sys.modules.get(qualified)
    if loaded is not None:
        return loaded
    key = "_socio_answer_sheet_map"
    loaded = sys.modules.get(key)
    if loaded is not None:
        return loaded
    path = Path(__file__).with_name("answer_sheet_map.py")
    spec = importlib.util.spec_from_file_location(key, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


def parse_card_qr(payload: Optional[str]) -> Optional[Dict[str, Any]]:
    """QR do cartão: prefixos e página no formato 2/3. A capa, sem página, não entra."""
    if not payload or not isinstance(payload, str):
        return None
    text = payload.strip()
    if not text.startswith("{") or "student_id" not in text or "form_id" not in text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if data.get("v") != 1:
        return None
    student_id = str(data.get("student_id") or "").strip()
    form_id = str(data.get("form_id") or "").strip()
    page_raw = data.get("p")
    if not student_id or not form_id or not isinstance(page_raw, str) or "/" not in page_raw:
        return None
    left, right = page_raw.split("/", 1)
    if not left.isdigit() or not right.isdigit():
        return None
    page = int(left)
    page_count = int(right)
    if page_count < 1 or page < 1 or page > page_count:
        return None
    return {
        "student_id": student_id,
        "form_id": form_id,
        "page": page,
        "page_count": page_count,
    }


def merge_marked_answers(existing: Optional[Dict[str, Any]], marked: Dict[str, Any]) -> Dict[str, Any]:
    """Grava só a chave marcada. Não apaga irmãs de uma matriz nem respostas em branco."""
    merged = dict(existing or {})
    for key, value in (marked or {}).items():
        if value is None or value == "":
            continue
        merged[str(key)] = value
    return merged


def prefix_matches(full_id: str, prefix: str) -> bool:
    full = str(full_id or "")
    text = str(prefix or "").strip()
    if not full or not text:
        return False
    if len(text) >= len(full):
        return text == full
    return full.startswith(text)


class SocioeconomicCardReader(AnswerSheetCorrectionNewGrid):
    """Mesma varredura de QR da prova física, com o JSON deste cartão."""

    def _is_valid_omr_qr_payload(self, payload: Optional[str]) -> bool:
        return parse_card_qr(payload) is not None

    def _parse_qr_payload(self, qr_data_str: str) -> Optional[Dict[str, Any]]:
        return parse_card_qr(qr_data_str)


def score_aligned_page(reader: SocioeconomicCardReader, aligned_bgr: np.ndarray, bubbles: List[Dict[str, Any]]):
    """Uma marca clara vira o texto da opção. Vazio e inválido não escolhem letra."""
    positions = _map_module()
    ink = reader._build_ink_strength_map(aligned_bgr)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for bubble in bubbles:
        grouped.setdefault(str(bubble["question_id"]), []).append(bubble)

    answers: Dict[str, str] = {}
    blank: List[str] = []
    invalid: List[str] = []
    for question_id, items in grouped.items():
        scored = []
        for item in items:
            x, y, radius = positions.bubble_to_a4_pixels(item["cx"], item["cy"], item["r"])
            score = reader._bubble_ink_score(ink, x, y, radius)
            scored.append({"letter": item["letter"], "score": score, "text": item["text"]})
        decision = reader._decide_question_mark_v2(scored)
        if decision is None:
            blank.append(question_id)
        elif decision == "INVALID":
            invalid.append(question_id)
        else:
            answers[question_id] = next(item["text"] for item in scored if item["letter"] == decision)
    return answers, blank, invalid


def read_card_image(image_bgr: np.ndarray, sheet_map: Dict[str, Any], reader: Optional[SocioeconomicCardReader] = None) -> Dict[str, Any]:
    """Uma imagem. Sem os quatro quadrados, a página é questionário e fica de fora."""
    reader = reader or SocioeconomicCardReader()
    anchors = reader._detect_a4_anchors(image_bgr)
    if not anchors:
        return {"status": "skipped", "reason": "sem quadrados de canto"}

    aligned = reader._normalize_to_a4(image_bgr, anchors)
    qr = reader._detectar_qr_code(aligned) or reader._detectar_qr_code(image_bgr)
    if not qr:
        return {"status": "error", "reason": "QR do cartão não lido"}
    if not prefix_matches(str(sheet_map.get("form_id") or ""), qr["form_id"]):
        return {"status": "error", "reason": "QR de outro formulário", "qr": qr}
    if int(qr["page_count"]) != int(sheet_map.get("page_count") or 0):
        return {
            "status": "error",
            "reason": "total de páginas do QR não confere com o cartão impresso",
            "qr": qr,
        }
    page_map = next((page for page in sheet_map.get("pages") or [] if page["page"] == qr["page"]), None)
    if page_map is None:
        return {"status": "error", "reason": "página do QR não existe no cartão", "qr": qr}

    answers, blank, invalid = score_aligned_page(reader, aligned, page_map["bubbles"])
    return {
        "status": "read",
        "qr": qr,
        "answers": answers,
        "blank": blank,
        "invalid": invalid,
        "aligned": aligned,
    }


def rasterize_pdf(pdf_bytes: bytes, dpi: int = _PDF_RASTER_DPI) -> List[np.ndarray]:
    from pdf2image import convert_from_bytes

    pages = convert_from_bytes(pdf_bytes, dpi=dpi)
    images = []
    for page in pages:
        rgb = np.array(page)
        images.append(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return images


def decode_image(raw: bytes) -> Optional[np.ndarray]:
    array = np.frombuffer(raw, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def pages_from_upload(filename: str, raw: bytes) -> List[np.ndarray]:
    if not raw:
        raise ValueError("arquivo vazio")
    if raw[:4] == b"%PDF" or (filename or "").lower().endswith(".pdf"):
        return rasterize_pdf(raw)
    image = decode_image(raw)
    if image is None:
        raise ValueError("arquivo de imagem inválido")
    return [image]


def _string_list(value: Any) -> List[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def payload_documents(payload: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Vários cartões no mesmo JSON: pdf, pdfs e images aceitam um valor ou uma lista."""
    if not isinstance(payload, dict):
        return []
    documents = []
    for key, filename in (("pdfs", "cartao.pdf"), ("pdf", "cartao.pdf"), ("images", "cartao.png")):
        for encoded in _string_list(payload.get(key)):
            documents.append({"filename": filename, "content": encoded})
    return documents


def correct_uploaded_sheets(
    form: Any,
    images: List[np.ndarray],
    city: Any = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    load_errors: Optional[List[Dict[str, Any]]] = None,
    file_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Lê várias folhas e grava uma correção por aluno no FormResponse."""
    counted = file_count if file_count is not None else len({
        item.get("fileIndex", 0) for item in (sources or [])
    })
    sheet_map = _map_module().build_answer_sheet_map(form, city)
    if not sheet_map["page_count"]:
        return {
            "formId": str(form.id),
            "pageCount": 0,
            "fileCount": counted,
            "students": [],
            "skipped": [],
            "errors": [{"reason": "este formulário não tem cartão de bolhas"}, *(load_errors or [])],
        }

    reader = SocioeconomicCardReader()
    skipped = []
    errors = list(load_errors or [])
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for index, image in enumerate(images):
        source = _page_source(sources, index)
        if image is None or getattr(image, "size", 0) == 0:
            errors.append({**source, "reason": "imagem vazia"})
            continue
        page = read_card_image(image, sheet_map, reader)
        page.pop("aligned", None)
        page.update(source)
        if page["status"] == "skipped":
            skipped.append({**source, "reason": page["reason"]})
        elif page["status"] == "error":
            errors.append({**source, "reason": page["reason"], "qr": page.get("qr")})
        else:
            buckets.setdefault(page["qr"]["student_id"], []).append(page)

    students = []
    for prefix, pages in buckets.items():
        students.append(_assemble_student(form, prefix, pages, sheet_map["page_count"]))

    return {
        "formId": str(form.id),
        "pageCount": sheet_map["page_count"],
        "fileCount": counted,
        "students": students,
        "skipped": skipped,
        "errors": errors,
    }


def _page_source(sources: Optional[List[Dict[str, Any]]], index: int) -> Dict[str, Any]:
    if sources and index < len(sources):
        source = sources[index]
        return {
            "fileIndex": source.get("fileIndex", 0),
            "pageIndex": source.get("pageIndex", index),
            "filename": source.get("filename") or "",
        }
    return {"fileIndex": 0, "pageIndex": index, "filename": ""}


def _assemble_student(form, prefix: str, pages: List[Dict[str, Any]], page_count: int) -> Dict[str, Any]:
    answers: Dict[str, str] = {}
    conflicts = []
    blank = []
    invalid = []
    seen = []
    for page in pages:
        seen.append(page["qr"]["page"])
        blank.extend(page["blank"])
        invalid.extend(page["invalid"])
        for key, value in page["answers"].items():
            previous = answers.get(key)
            if previous is not None and previous != value:
                conflicts.append(key)
                continue
            answers[key] = value

    stored = save_marked_answers(form, prefix, answers)
    present = sorted(set(seen))
    return {
        **stored,
        "answers": answers,
        "blank": sorted(set(blank) - set(answers)),
        "invalid": sorted(set(invalid)),
        "conflicts": sorted(set(conflicts)),
        "pages": present,
        "missingPages": [number for number in range(1, page_count + 1) if number not in present],
        "files": sorted({page.get("fileIndex") for page in pages if page.get("fileIndex") is not None}),
    }


def save_marked_answers(form, student_prefix: str, answers: Dict[str, str]) -> Dict[str, Any]:
    """Grava no formulário existente. Sem user_id, devolve a leitura e não grava."""
    from app import db
    from app.models.student import Student
    from app.socioeconomic_forms.models.form_recipient import FormRecipient
    from app.socioeconomic_forms.models.form_response import FormResponse
    from app.socioeconomic_forms.services.distribution_service import DistributionService

    result = {
        "studentPrefix": student_prefix,
        "studentId": None,
        "userId": None,
        "saved": False,
        "reason": None,
        "responseId": None,
    }
    matches = Student.query.filter(Student.id.startswith(student_prefix)).limit(2).all()
    if len(matches) != 1:
        result["reason"] = "prefixo de aluno ambíguo ou inexistente"
        return result
    student = matches[0]
    result["studentId"] = str(student.id)
    if not prefix_matches(student.id, student_prefix):
        result["reason"] = "prefixo de aluno ambíguo ou inexistente"
        return result
    if not student.user_id:
        result["reason"] = "aluno sem usuário vinculado"
        return result
    result["userId"] = str(student.user_id)

    if not form.is_active:
        result["reason"] = "formulário não está ativo"
        return result
    if form.deadline and datetime.utcnow() > form.deadline:
        result["reason"] = "prazo para responder este questionário expirou"
        return result

    try:
        DistributionService.ensure_recipients_for_student(student, commit=False)
        recipient = FormRecipient.query.filter_by(form_id=form.id, user_id=student.user_id).first()
        if not recipient:
            result["reason"] = "aluno fora do escopo deste questionário"
            return result

        response = FormResponse.query.filter_by(form_id=form.id, user_id=student.user_id).first()
        merged = merge_marked_answers(response.responses if response else {}, answers)
        if response is None:
            response = FormResponse(
                form_id=form.id,
                user_id=student.user_id,
                recipient_id=recipient.id,
                status="in_progress",
                responses=merged,
                started_at=datetime.utcnow(),
            )
            db.session.add(response)
            if recipient.status == "pending":
                recipient.status = "in_progress"
                recipient.started_at = datetime.utcnow()
        else:
            response.responses = merged
            response.updated_at = datetime.utcnow()

        response.progress = _progress(form, merged)
        try:
            from app.socioeconomic_forms.services.results_cache_service import ResultsCacheService
            ResultsCacheService.mark_dirty_for_response(response, commit=False)
        except Exception as cache_error:
            logger.warning("Erro ao marcar caches como dirty: %s", cache_error)

        db.session.commit()
        result["saved"] = True
        result["responseId"] = str(response.id)
        return result
    except Exception as exc:
        db.session.rollback()
        logger.exception("Falha ao gravar o cartão socioeconômico")
        result["reason"] = str(exc)
        return result


def _progress(form, responses: Dict[str, Any]) -> float:
    questions = list(form.questions or [])
    if not questions:
        return 0.0
    answered = 0
    for question in questions:
        subs = question.sub_questions or []
        if subs:
            complete = True
            for sub in subs:
                sub_id = sub.get("id") if isinstance(sub, dict) else None
                value = responses.get(sub_id) if sub_id else None
                if value is None or value == "":
                    complete = False
                    break
            if complete:
                answered += 1
        else:
            value = responses.get(question.question_id)
            if value is not None and value != "":
                answered += 1
    return round(answered / len(questions) * 100, 2)
