# -*- coding: utf-8 -*-
"""
Leitura do cartão-resposta da avaliação escrita do Afirme Ler.

O alinhamento da folha é o do socioeconômico: quatro quadrados dos cantos e a
decisão de tinta das bolhas. O quadrado preto de cada questão desloca a linha
antes de ler a bolha ou recortar o ditado e o bilhete. A nota desses recortes
não é calculada aqui.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app import db
from app.afirme_ler.models.reading_written_test import (
    ReadingWrittenTestCorrection,
    ReadingWrittenTestPrintRun,
)
from app.afirme_ler.services.written_test_answer_sheet_service import BUCKET_KEY, MAP_VERSION
from app.socioeconomic_forms.services.answer_sheet_correction import (
    SocioeconomicCardReader,
    pages_from_upload,
    payload_documents,
    prefix_matches,
    student_display_name,
)

ANCHOR_WINDOW_PX = 40
_MIN_DARK_PIXELS = 8


def parse_card_qr(payload: Optional[str]) -> Optional[Dict[str, Any]]:
    """QR do cartão: prefixos de aluno e da avaliação, página no formato 2/3."""
    if not payload or not isinstance(payload, str):
        return None
    text = payload.strip()
    if not text.startswith("{") or "student_id" not in text or "written_test_id" not in text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if data.get("v") != 1:
        return None
    student_id = str(data.get("student_id") or "").strip()
    written_test_id = str(data.get("written_test_id") or "").strip()
    page_raw = data.get("p")
    if not student_id or not written_test_id or not isinstance(page_raw, str) or "/" not in page_raw:
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
        "written_test_id": written_test_id,
        "page": page,
        "page_count": page_count,
    }


class WrittenTestCardReader(SocioeconomicCardReader):
    """Varredura de QR da prova física, com o JSON deste cartão."""

    def _is_valid_omr_qr_payload(self, payload: Optional[str]) -> bool:
        return parse_card_qr(payload) is not None

    def _parse_qr_payload(self, qr_data_str: str) -> Optional[Dict[str, Any]]:
        return parse_card_qr(qr_data_str)


def latest_answer_sheet_map(written_test_id: str) -> Dict[str, Any]:
    """Mapa mais recente que já tem o quadrado de cada questão."""
    runs = (
        ReadingWrittenTestPrintRun.query
        .filter(ReadingWrittenTestPrintRun.written_test_id == str(written_test_id))
        .order_by(ReadingWrittenTestPrintRun.created_at.desc(), ReadingWrittenTestPrintRun.id.desc())
        .all()
    )
    for run in runs:
        sheet = run.answer_sheet_map or {}
        if sheet.get("error") or sheet.get("version") != MAP_VERSION:
            continue
        if any(page.get("row_anchors") for page in sheet.get("pages") or []):
            return sheet
    raise ValueError(
        "Gere os cartões-resposta de novo antes de corrigir. "
        "O mapa não tem o quadrado de cada questão."
    )


def _dark_centroid(image: np.ndarray, x: int, y: int, window: int = ANCHOR_WINDOW_PX) -> Optional[Tuple[int, int]]:
    """Centro da mancha escura em volta do quadrado esperado. None se não houver mancha."""
    height, width = image.shape[:2]
    x1, y1 = max(0, int(x) - window), max(0, int(y) - window)
    x2, y2 = min(width, int(x) + window), min(height, int(y) + window)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    crop = image[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    dark = gray < 80
    if int(dark.sum()) < _MIN_DARK_PIXELS:
        return None
    ys, xs = np.nonzero(dark)
    return x1 + int(round(float(xs.mean()))), y1 + int(round(float(ys.mean())))


def anchor_shift(image: np.ndarray, anchor: Dict[str, Any]) -> Tuple[int, int]:
    """Deslocamento do quadrado achado em relação ao mapa. Sem quadrado, a linha não se move."""
    pixel = anchor.get("pixel") or {}
    expected_x = int(pixel.get("x") or 0)
    expected_y = int(pixel.get("y") or 0)
    found = _dark_centroid(image, expected_x, expected_y)
    if found is None:
        return 0, 0
    return found[0] - expected_x, found[1] - expected_y


def _crop_png(image: np.ndarray, pixel: Dict[str, Any], dx: int, dy: int) -> Optional[bytes]:
    x = int(pixel.get("x") or 0) + int(dx)
    y = int(pixel.get("y") or 0) + int(dy)
    width = int(pixel.get("width") or 0)
    height = int(pixel.get("height") or 0)
    if width < 2 or height < 2:
        return None
    image_h, image_w = image.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(image_w, x + width), min(image_h, y + height)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    ok, encoded = cv2.imencode(".png", image[y1:y2, x1:x2])
    if not ok:
        return None
    return encoded.tobytes()


def interpret_aligned_page(
    aligned: np.ndarray,
    page_map: Dict[str, Any],
    reader: Optional[WrittenTestCardReader] = None,
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Letras das bolhas e PNG das áreas de escrita desta folha, já alinhada."""
    reader = reader or WrittenTestCardReader()
    ink = reader._build_ink_strength_map(aligned)
    shifts = {
        anchor["question_id"]: anchor_shift(aligned, anchor)
        for anchor in page_map.get("row_anchors") or []
    }

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for bubble in page_map.get("bubbles") or []:
        grouped.setdefault(bubble["question_id"], []).append(bubble)

    answers: Dict[str, Dict[str, Any]] = {}
    blank: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []
    for question_id, bubbles in grouped.items():
        dx, dy = shifts.get(question_id, (0, 0))
        scored = []
        number = bubbles[0]["number"]
        for bubble in bubbles:
            pixel = bubble["pixel"]
            score = reader._bubble_ink_score(
                ink,
                int(pixel["x"]) + dx,
                int(pixel["y"]) + dy,
                int(pixel["r"]),
            )
            scored.append({"letter": bubble["letter"], "score": score})
        decision = reader._decide_question_mark_v2(scored)
        if decision is None:
            blank.append({"number": number, "questionId": question_id})
        elif decision == "INVALID":
            invalid.append({"number": number, "questionId": question_id})
        else:
            answers[question_id] = {"number": number, "letter": decision}

    crops: Dict[str, Dict[str, Any]] = {}
    for area in page_map.get("writing_areas") or []:
        dx, dy = shifts.get(area["question_id"], (0, 0))
        png = _crop_png(aligned, area.get("pixel") or {}, dx, dy)
        if png is None:
            continue
        crops[area["question_id"]] = {"number": area["number"], "type": area["type"], "png": png}
    return answers, blank, invalid, crops


def read_card_image(
    image_bgr: np.ndarray,
    sheet_map: Dict[str, Any],
    reader: Optional[WrittenTestCardReader] = None,
) -> Dict[str, Any]:
    """Uma imagem. Sem os quatro quadrados, a página fica de fora."""
    reader = reader or WrittenTestCardReader()
    anchors = reader._detect_a4_anchors(image_bgr)
    if not anchors:
        return {"status": "skipped", "reason": "sem quadrados de canto"}

    aligned = reader._normalize_to_a4(image_bgr, anchors)
    qr = reader._detectar_qr_code(aligned) or reader._detectar_qr_code(image_bgr)
    if not qr:
        return {"status": "error", "reason": "QR do cartão não lido"}
    if not prefix_matches(str(sheet_map.get("written_test_id") or ""), qr["written_test_id"]):
        return {"status": "error", "reason": "QR de outra avaliação", "qr": qr}
    if int(qr["page_count"]) != int(sheet_map.get("page_count") or 0):
        return {
            "status": "error",
            "reason": "total de páginas do QR não confere com o cartão impresso",
            "qr": qr,
        }
    page_map = next((page for page in sheet_map.get("pages") or [] if page["page"] == qr["page"]), None)
    if page_map is None:
        return {"status": "error", "reason": "página do QR não existe no cartão", "qr": qr}

    answers, blank, invalid, crops = interpret_aligned_page(aligned, page_map, reader)
    return {
        "status": "read",
        "qr": qr,
        "answers": answers,
        "blank": blank,
        "invalid": invalid,
        "crops": crops,
        "aligned": aligned,
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


def _without(items: List[Dict[str, Any]], question_id: str) -> List[Dict[str, Any]]:
    return [item for item in items if item.get("questionId") != question_id]


def _merge_page(stored: Dict[str, Any], page: Dict[str, Any]) -> None:
    """A folha substitui só as questões que ela contém. A outra folha permanece."""
    answers = dict(stored["answers"])
    blank = list(stored["blank"])
    invalid = list(stored["invalid"])
    crops = dict(stored["crops"])
    touched = set(page["answers"]) | {item["questionId"] for item in page["blank"]} | {
        item["questionId"] for item in page["invalid"]
    }
    for question_id in touched:
        answers.pop(question_id, None)
        blank = _without(blank, question_id)
        invalid = _without(invalid, question_id)
    answers.update(page["answers"])
    blank.extend(page["blank"])
    invalid.extend(page["invalid"])
    for question_id, crop in page["crops"].items():
        previous = crops.get(question_id) or {}
        crops[question_id] = {
            "number": crop["number"],
            "type": crop.get("type") or previous.get("type"),
            "bucket": previous.get("bucket"),
            "objectName": previous.get("objectName"),
            "saved": bool(previous.get("saved")),
            "png": crop.get("png"),
        }
    stored["answers"] = answers
    stored["blank"] = blank
    stored["invalid"] = invalid
    stored["crops"] = crops
    stored["pages"] = sorted(set(stored["pages"]) | {page["qr"]["page"]})


def _upload_crops(written_test_id: str, student_id: str, crops: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    from app.services.storage.minio_service import MinIOService

    pending = {key: value for key, value in crops.items() if value.get("png")}
    if not pending:
        return {key: {k: v for k, v in value.items() if k != "png"} for key, value in crops.items()}

    storage = MinIOService()
    bucket = MinIOService.BUCKETS[BUCKET_KEY]
    stored = {}
    for question_id, crop in crops.items():
        entry = {k: v for k, v in crop.items() if k != "png"}
        png = crop.get("png")
        if not png:
            stored[question_id] = entry
            continue
        number = int(crop["number"])
        object_name = (
            f"afirme-ler/written-tests/{written_test_id}/corrections/{student_id}/q{number:02d}.png"
        )
        uploaded = storage.upload_file(bucket, object_name, png, content_type="image/png")
        entry["bucket"] = bucket
        entry["objectName"] = object_name if uploaded else None
        entry["saved"] = uploaded is not None
        stored[question_id] = entry
    return stored


def _public_crops(crops: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = []
    for question_id, crop in crops.items():
        items.append({
            "number": crop.get("number"),
            "questionId": question_id,
            "saved": bool(crop.get("saved")),
        })
    return sorted(items, key=lambda item: item["number"] or 0)


def _public_answers(answers: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = [
        {"number": value["number"], "questionId": question_id, "letter": value["letter"]}
        for question_id, value in answers.items()
    ]
    return sorted(items, key=lambda item: item["number"])


def save_student_pages(
    written_test_id: str,
    student_prefix: str,
    pages: List[Dict[str, Any]],
    page_count: int,
) -> Dict[str, Any]:
    """Grava uma correção por aluno. Junta as folhas e substitui o recorte reenviado."""
    from app.models.student import Student

    result = {
        "studentPrefix": student_prefix,
        "studentId": None,
        "studentName": None,
        "saved": False,
        "reason": None,
    }
    matches = Student.query.filter(Student.id.startswith(student_prefix)).limit(2).all()
    if len(matches) != 1 or not prefix_matches(matches[0].id, student_prefix):
        result["reason"] = "prefixo de aluno ambíguo ou inexistente"
        return result
    student = matches[0]
    result["studentId"] = str(student.id)
    result["studentName"] = student_display_name(student)

    row = ReadingWrittenTestCorrection.query.filter_by(
        written_test_id=str(written_test_id), student_id=str(student.id),
    ).first()
    stored = {
        "answers": dict(row.answers or {}) if row else {},
        "blank": list(row.blank or []) if row else [],
        "invalid": list(row.invalid or []) if row else [],
        "crops": dict(row.crops or {}) if row else {},
        "pages": list(row.pages or []) if row else [],
    }
    for page in pages:
        _merge_page(stored, page)
    stored["crops"] = _upload_crops(written_test_id, str(student.id), stored["crops"])
    from app.afirme_ler.services.written_test_writing_grade import (
        public_objective,
        score_multiple_choice,
    )

    objective = score_multiple_choice(
        written_test_id, stored["answers"], stored["blank"], stored["invalid"],
    )

    if row is None:
        row = ReadingWrittenTestCorrection(
            written_test_id=str(written_test_id),
            student_id=str(student.id),
        )
        db.session.add(row)
    row.answers = stored["answers"]
    row.blank = stored["blank"]
    row.invalid = stored["invalid"]
    row.crops = stored["crops"]
    row.pages = stored["pages"]
    row.objective = objective
    db.session.commit()

    present = stored["pages"]
    result.update({
        "saved": True,
        "correctionId": row.id,
        "answers": _public_answers(stored["answers"]),
        "blank": sorted(stored["blank"], key=lambda item: item["number"]),
        "invalid": sorted(stored["invalid"], key=lambda item: item["number"]),
        "crops": _public_crops(stored["crops"]),
        "pages": present,
        "missingPages": [number for number in range(1, page_count + 1) if number not in present],
        "objective": public_objective(objective),
    })
    return result


def correct_uploaded_sheets(
    written_test_id: str,
    images: List[np.ndarray],
    sources: Optional[List[Dict[str, Any]]] = None,
    load_errors: Optional[List[Dict[str, Any]]] = None,
    file_count: Optional[int] = None,
    sheet_map: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Lê várias folhas e grava uma correção por aluno."""
    counted = file_count if file_count is not None else len({
        item.get("fileIndex", 0) for item in (sources or [])
    })
    sheet = sheet_map or latest_answer_sheet_map(written_test_id)
    reader = WrittenTestCardReader()
    skipped = []
    errors = list(load_errors or [])
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for index, image in enumerate(images):
        source = _page_source(sources, index)
        if image is None or getattr(image, "size", 0) == 0:
            errors.append({**source, "reason": "imagem vazia"})
            continue
        page = read_card_image(image, sheet, reader)
        page.pop("aligned", None)
        page.update(source)
        if page["status"] == "skipped":
            skipped.append({**source, "reason": page["reason"]})
        elif page["status"] == "error":
            errors.append({**source, "reason": page["reason"], "qr": page.get("qr")})
        else:
            buckets.setdefault(page["qr"]["student_id"], []).append(page)

    from app.afirme_ler.services.written_test_writing_grade import grade_scanned_writing

    students = []
    for prefix, pages in buckets.items():
        saved = save_student_pages(written_test_id, prefix, pages, int(sheet.get("page_count") or 0))
        if saved["saved"]:
            saved["writing"] = grade_scanned_writing(written_test_id, saved["studentId"], pages)
        students.append(saved)
    return {
        "writtenTestId": str(written_test_id),
        "pageCount": int(sheet.get("page_count") or 0),
        "fileCount": counted,
        "students": students,
        "skipped": skipped,
        "errors": errors,
    }


def load_correction_batch(request) -> Tuple[List[np.ndarray], List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """Vários PDFs ou imagens na mesma chamada. Um arquivo inválido não cancela os outros."""
    images: List[np.ndarray] = []
    sources: List[Dict[str, Any]] = []
    load_errors: List[Dict[str, Any]] = []
    file_index = 0

    def take_file(filename, raw, decode_error=None):
        nonlocal file_index
        current = file_index
        file_index += 1
        if decode_error:
            load_errors.append({"fileIndex": current, "filename": filename, "reason": decode_error})
            return
        try:
            pages = pages_from_upload(filename, raw)
        except ValueError as exc:
            load_errors.append({"fileIndex": current, "filename": filename, "reason": str(exc)})
            return
        for page_index, image in enumerate(pages):
            images.append(image)
            sources.append({"fileIndex": current, "pageIndex": page_index, "filename": filename})

    for field in request.files:
        for storage in request.files.getlist(field):
            take_file(storage.filename or "", storage.read())

    payload = request.get_json(silent=True) or {}
    for document in payload_documents(payload):
        filename = document["filename"]
        try:
            raw = _decode_base64(document["content"])
        except Exception:
            take_file(filename, b"", "conteúdo do arquivo inválido")
            continue
        take_file(filename, raw)

    return images, sources, load_errors, file_index


def _decode_base64(value: str) -> bytes:
    import base64

    text = value.strip()
    if "," in text and text.startswith("data:"):
        text = text.split(",", 1)[1]
    return base64.b64decode(text)
