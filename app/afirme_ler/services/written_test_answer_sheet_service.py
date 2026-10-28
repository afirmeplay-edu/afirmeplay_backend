# -*- coding: utf-8 -*-
"""
Cartões-resposta da avaliação escrita do Afirme Ler.

Mesmo desenho do pacote impresso do socioeconômico, com tabela própria (reading_written_test_print_run):
  - PDF base renderizado uma vez (afirme_ler_written_answer_sheet.html, WeasyPrint);
  - overlay por aluno (ReportLab): cabeçalho com título, aluno, escola, série/turma, assinatura/data e
    QR {"v":1,"student_id":<12>,"written_test_id":<12>,"p":"n/N"} em cada folha;
  - mapa do cartão extraído do PDF base (bolhas, quadrado de cada questão e áreas de escrita), guardado no run;
  - ZIP com um PDF por aluno (pdf_arcname: pastas município/escola/série/turma, sufixo do id contra
    homônimos), enviado ao MinIO pela task Celery.
Não usa o cartão nem a task da prova física do Play.
"""
from __future__ import annotations

import io
import logging
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from app import db
from app.models.question import Question
from app.afirme_ler.models.reading_written_test import (
    PRINT_RUN_DONE,
    PRINT_RUN_ERROR,
    PRINT_RUN_PENDING,
    PRINT_RUN_PROCESSING,
    WRITTEN_TEST_STATUS_PUBLISHED,
    ReadingWrittenTest,
    ReadingWrittenTestPrintRun,
)
from app.afirme_ler.services.question_bank_service import (
    QUESTION_TYPE_DICTATION,
    QUESTION_TYPE_MULTIPLE_CHOICE,
    QUESTION_TYPE_TEXT_PRODUCTION,
)
from app.afirme_ler.services.written_test_pdf_service import _parse_alternatives
from app.afirme_ler.services.written_test_service import (
    WrittenTestService,
    _assert_allowed_type,
    _class_label,
    _type_key,
    _user_id,
    _uuid_or_none,
)

logger = logging.getLogger(__name__)

TEMPLATE_NAME = "afirme_ler_written_answer_sheet.html"
WRITING_LINES = 15
MAX_LETTERS = 8
ACTIVE_STATUSES = (PRINT_RUN_PENDING, PRINT_RUN_PROCESSING)
# Geração 'pendente'/'processando' mais velha que isso não bloqueia outra (worker caiu, por exemplo).
STALE_SECONDS = 30 * 60
PROGRESS_EVERY = 25
BUCKET_KEY = "AFIRME_READING_AUDIO"
QR_PAYLOAD_VERSION = 1
MAP_VERSION = 2

# Tamanhos em px CSS. O template os recebe daqui; o mapa reconhece cada desenho por eles.
SIZES = {
    "bubble": 12,
    "anchor": 8,
    "dictation_w": 340,
    "dictation_h": 44,
    "production_w": 660,
    "production_line": 32,
    "production_h": WRITING_LINES * 32 + 2,
}
_SIZE_TOLERANCE = 0.6

# Mesma bolha do cartão do socioeconômico (48x48 desenhado em 12px).
BUBBLE_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAABIklEQVR4nO2ZSQ7DIAxFQ+9/Z7JKxOARgg2Ut+si9vsYIRWu"
    "63DoIgyoGS17flGMEx7q0PNxr3hJk0trAFQ+RjpXCGRLtY/2A9COk0ab42HEXpoAlWWreCUBBxG5SQNkpl+JlwBBWL+foK6J"
    "PFKbbcYFMJMnepBNJRPACg9D04sK8FaxlEd6ogJYAHtjHtCJ3UIeq6/pDQWYcfUfKjdyAp6rL3UQn0Kzsl0A16MTgzpSt5vA"
    "cpwA3pwA3mwX4P0Lx9wemFK4ZD+2m8BykAFm2EacAxTA3xqncmO3kOcUJL2xADNOAXSiJuB6pFJHZ4r4FLIMoenFBciXwSCE"
    "9n5UMgGzEC2Xu39zvf6w9ANHyrJPTClLP/KlLPvMimH60H04dHIDaVhYSMr0sDoAAAAASUVORK5CYII="
)
# Fundo branco 1x1 das áreas de escrita: invisível no papel, marca o retângulo no PDF.
AREA_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mP4//8/AAX+Av4zEpUUAAAAAElFTkSuQmCC"
# Quadrado preto de 8px, um por questão. Tamanho diferente da bolha para o mapa separar os dois.
ANCHOR_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAADElEQVR4nGNgGB4AAADIAAGtQHYiAAAAAElFTkSuQmCC"

# Overlay do cabeçalho, em pt, origem no canto inferior esquerdo da A4 (595,28 x 841,89).
# A margem de cima do template (4,6cm) deixa a faixa livre. Os quadrados de 32px ficam a 0,2cm dos
# cantos (x < 29,7 e x > 565,6; y > 812,2): caixa e QR ficam fora deles.
_BOX_X = 42.52
_BOX_Y = 716.0
_BOX_W = 510.24
_BOX_H = 94.0
_QR_SIZE = 66.0
_QR_X = _BOX_X + _BOX_W - 6.0 - _QR_SIZE
_QR_Y = _BOX_Y + 14.0
_TEXT_X = 50.0
_VALUE_X = 128.0
_Y_TITLE = 794.0
_Y_STUDENT = 777.0
_Y_SCHOOL = 762.0
_Y_CLASS = 747.0
_Y_SIGNATURE = 727.0


class GenerationInProgress(Exception):
    def __init__(self, run: ReadingWrittenTestPrintRun):
        super().__init__("Já existe uma geração de cartões em andamento para esta avaliação/turma.")
        self.run = run


def _utcnow() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Dados do cartão (sem gabarito, sem palavra ditada, sem pontuação)
# ---------------------------------------------------------------------------

def build_card_items(written_test: ReadingWrittenTest) -> List[Dict[str, Any]]:
    if written_test.status != WRITTEN_TEST_STATUS_PUBLISHED:
        raise ValueError("Só avaliação publicada pode gerar os cartões-resposta.")

    links = sorted(written_test.questions or [], key=lambda link: link.order)
    ids = [link.question_id for link in links]
    found = {q.id: q for q in Question.query.filter(Question.id.in_(ids)).all()} if ids else {}

    items = []
    for number, link in enumerate(links, start=1):
        question = found.get(link.question_id)
        if question is None:
            raise ValueError(
                f"A questão {link.question_id} (posição {link.order}) não existe mais no banco "
                "de questões. Não é possível gerar os cartões-resposta."
            )
        _assert_allowed_type(question)
        question_type = _type_key(question.question_type)
        item: Dict[str, Any] = {"number": number, "question_id": question.id, "type": question_type}
        if question_type == QUESTION_TYPE_MULTIPLE_CHOICE:
            count = min(len(_parse_alternatives(question.alternatives)), MAX_LETTERS)
            if count < 1:
                raise ValueError(f"A questão {number} ({question.id}) não tem alternativas.")
            item["letters"] = [chr(65 + index) for index in range(count)]
        elif question_type == QUESTION_TYPE_TEXT_PRODUCTION:
            item["lines"] = WRITING_LINES
        items.append(item)
    return items


def card_template_context(
    written_test: ReadingWrittenTest, items: List[Dict[str, Any]], preview: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return {
        "test": {"title": written_test.title},
        "items": items,
        "sizes": SIZES,
        "bubble_png": BUBBLE_PNG,
        "anchor_png": ANCHOR_PNG,
        "area_png": AREA_PNG,
        "preview": preview,
    }


def _generator(generator: Any = None):
    if generator is not None:
        return generator
    from app.services.institutional_test_weasyprint_generator import (
        InstitutionalTestWeasyPrintGenerator,
    )

    return InstitutionalTestWeasyPrintGenerator()


def render_card_html(
    written_test: ReadingWrittenTest,
    items: List[Dict[str, Any]],
    generator: Any = None,
    preview: Optional[Dict[str, Any]] = None,
) -> str:
    return _generator(generator)._render_template(
        TEMPLATE_NAME, card_template_context(written_test, items, preview)
    )


def render_base_pdf(written_test: ReadingWrittenTest, items: List[Dict[str, Any]], generator: Any = None) -> bytes:
    generator = _generator(generator)
    return generator._html_to_pdf_bytes(render_card_html(written_test, items, generator))


# ---------------------------------------------------------------------------
# QR e overlay por aluno
# ---------------------------------------------------------------------------

def build_qr_payload(student_id: str, written_test_id: str, page: int, page_count: int) -> Dict[str, Any]:
    """Mesmo formato curto do socioeconômico: prefixos de 12 caracteres e a folha em "p"."""
    from app.socioeconomic_forms.services.questionnaire_individual_pdf import qr_id_prefix

    student = qr_id_prefix(student_id)
    test = qr_id_prefix(written_test_id)
    if not student or not test:
        raise ValueError("student_id e written_test_id são obrigatórios no QR Code")
    if page_count < 1 or page < 1 or page > page_count:
        raise ValueError("página do cartão fora do intervalo")
    return {
        "v": QR_PAYLOAD_VERSION,
        "student_id": student,
        "written_test_id": test,
        "p": f"{int(page)}/{int(page_count)}",
    }


def qr_text(student_id: str, written_test_id: str, page: int, page_count: int) -> str:
    from app.socioeconomic_forms.services.questionnaire_individual_pdf import qr_payload_text

    return qr_payload_text(build_qr_payload(student_id, written_test_id, page, page_count))


def _class_line(grade_name: str, class_name: str) -> str:
    grade = (grade_name or "").strip()
    klass = (class_name or "").strip()
    if grade and klass:
        return f"{grade} - {klass}"
    return grade or klass


def render_overlay_pdf(
    *,
    page_count: int,
    student_id: str,
    written_test_id: str,
    title: str = "",
    student_name: str = "",
    school_name: str = "",
    grade_name: str = "",
    class_name: str = "",
) -> bytes:
    """Uma página de overlay por folha do cartão. Aluno igual em todas; o QR muda em "p"."""
    from reportlab.lib.colors import black
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    from app.socioeconomic_forms.services.questionnaire_individual_pdf import (
        _draw_fitted,
        build_qr_code,
    )

    total = max(int(page_count), 1)
    value_width = _QR_X - 8.0 - _VALUE_X
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=A4)
    for page in range(1, total + 1):
        canvas.setStrokeColor(black)
        canvas.setFillColor(black)
        canvas.setLineWidth(0.8)
        canvas.rect(_BOX_X, _BOX_Y, _BOX_W, _BOX_H, stroke=1, fill=0)

        _draw_fitted(canvas, title or "", _TEXT_X, _Y_TITLE, _QR_X - 8.0 - _TEXT_X, "Helvetica-Bold", 11)
        for label, value, y in (
            ("Aluno:", (student_name or "").upper(), _Y_STUDENT),
            ("Escola:", (school_name or "").upper(), _Y_SCHOOL),
            ("Série/Turma:", _class_line(grade_name, class_name).upper(), _Y_CLASS),
        ):
            canvas.setFont("Helvetica", 8)
            canvas.drawString(_TEXT_X, y, label)
            _draw_fitted(canvas, value, _VALUE_X, y, value_width, "Helvetica-Bold", 10)

        canvas.setFont("Helvetica", 8)
        canvas.drawString(_TEXT_X, _Y_SIGNATURE, "Assinatura:")
        canvas.line(100.0, _Y_SIGNATURE - 1.5, 318.0, _Y_SIGNATURE - 1.5)
        canvas.drawString(330.0, _Y_SIGNATURE, "Data:")
        canvas.line(355.0, _Y_SIGNATURE - 1.5, 470.0, _Y_SIGNATURE - 1.5)

        qr = build_qr_code(qr_text(student_id, written_test_id, page, total))
        image = qr.make_image(fill_color="black", back_color="white")
        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        image_buffer.seek(0)
        canvas.drawImage(
            ImageReader(image_buffer), _QR_X, _QR_Y, width=_QR_SIZE, height=_QR_SIZE,
            preserveAspectRatio=True, mask="auto",
        )
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawCentredString(_QR_X + _QR_SIZE / 2.0, _BOX_Y + 5.0, f"FOLHA {page} DE {total}")
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def personalize_answer_sheet_pdf(base_pdf: bytes, *, page_count: int, **student: Any) -> bytes:
    from app.socioeconomic_forms.services.questionnaire_individual_pdf import apply_card_overlays

    overlay = render_overlay_pdf(page_count=page_count, **student)
    return apply_card_overlays(base_pdf, overlay, 0)


# ---------------------------------------------------------------------------
# Mapa do cartão (para a correção futura)
# ---------------------------------------------------------------------------

_NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)$")


def _close(value: float, expected: float) -> bool:
    return abs(abs(value) - expected) <= _SIZE_TOLERANCE


def _mark_kind(width: float, height: float) -> Optional[str]:
    if _close(width, SIZES["anchor"]) and _close(height, SIZES["anchor"]):
        return "anchor"
    if _close(width, SIZES["bubble"]) and _close(height, SIZES["bubble"]):
        return "bubble"
    if _close(width, SIZES["dictation_w"]) and _close(height, SIZES["dictation_h"]):
        return QUESTION_TYPE_DICTATION
    if _close(width, SIZES["production_w"]) and _close(height, SIZES["production_h"]):
        return QUESTION_TYPE_TEXT_PRODUCTION
    return None


def extract_marks_from_content(content: str) -> List[Dict[str, Any]]:
    """Retângulos com imagem (re ... Do) dos tamanhos do cartão, em pt, na ordem do desenho."""
    from app.socioeconomic_forms.services.answer_sheet_map import _apply, _multiply

    tokens = content.split()
    identity = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    ctm = identity
    stack = [identity]
    last_rect: Optional[Tuple[float, ...]] = None
    marks: List[Dict[str, Any]] = []
    for index, token in enumerate(tokens):
        if token == "q":
            stack.append(ctm)
        elif token == "Q" and len(stack) > 1:
            ctm = stack.pop()
        elif token == "cm" and index >= 6 and all(_NUMBER.match(tokens[index - 6 + i]) for i in range(6)):
            ctm = _multiply(ctm, tuple(float(tokens[index - 6 + i]) for i in range(6)))
        elif token == "re" and index >= 4 and all(_NUMBER.match(tokens[index - 4 + i]) for i in range(4)):
            last_rect = tuple(float(tokens[index - 4 + i]) for i in range(4))
        elif token == "Do" and last_rect is not None:
            x, y, width, height = last_rect
            last_rect = None
            kind = _mark_kind(width, height)
            if kind is None:
                continue
            x1, y1 = _apply(ctm, x, y)
            x2, y2 = _apply(ctm, x + width, y + height)
            marks.append({
                "kind": kind,
                "left": min(x1, x2), "right": max(x1, x2),
                "bottom": min(y1, y2), "top": max(y1, y2),
            })
    return marks


def expected_marks(
    items: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    bubbles, areas, anchors = [], [], []
    for item in items:
        anchors.append({
            "number": item["number"], "question_id": item["question_id"], "type": item["type"],
        })
        if item["type"] == QUESTION_TYPE_MULTIPLE_CHOICE:
            for index, letter in enumerate(item["letters"]):
                bubbles.append({
                    "number": item["number"], "question_id": item["question_id"],
                    "letter": letter, "option_index": index,
                })
        else:
            areas.append({"number": item["number"], "question_id": item["question_id"], "type": item["type"]})
    return bubbles, areas, anchors


def _pixels(x: float, y: float) -> Tuple[int, int]:
    from app.socioeconomic_forms.services.answer_sheet_map import bubble_to_a4_pixels

    px, py, _ = bubble_to_a4_pixels(x, y, 1.0)
    return px, py


def build_answer_sheet_map_from_pages(
    page_contents: List[str], items: List[Dict[str, Any]], written_test_id: str
) -> Dict[str, Any]:
    """
    Bolhas, quadrados e áreas são casados com a avaliação separadamente: o WeasyPrint pinta os
    fundos de bloco (áreas) antes dos inline-block (quadrado e bolhas), mas cada grupo sai na
    ordem do template.
    """
    from app.socioeconomic_forms.services.answer_sheet_map import (
        A4_HEIGHT_PX,
        A4_WIDTH_PX,
        bubble_to_a4_pixels,
    )

    expected_bubbles, expected_areas, expected_anchors = expected_marks(items)
    found_bubbles, found_areas, found_anchors = [], [], []
    buckets = {"bubble": found_bubbles, "anchor": found_anchors}
    for page_number, content in enumerate(page_contents, start=1):
        for mark in extract_marks_from_content(content):
            target = buckets.get(mark["kind"], found_areas)
            target.append({**mark, "page": page_number})

    if len(found_bubbles) != len(expected_bubbles):
        raise ValueError(
            f"O cartão desenhou {len(found_bubbles)} bolhas e a avaliação tem {len(expected_bubbles)}."
        )
    if len(found_areas) != len(expected_areas):
        raise ValueError(
            f"O cartão desenhou {len(found_areas)} áreas de escrita e a avaliação tem {len(expected_areas)}."
        )
    if len(found_anchors) != len(expected_anchors):
        raise ValueError(
            f"O cartão desenhou {len(found_anchors)} quadrados de questão e a avaliação tem "
            f"{len(expected_anchors)}."
        )

    pages = {
        n: {"page": n, "bubbles": [], "writing_areas": [], "row_anchors": []}
        for n in range(1, len(page_contents) + 1)
    }
    for mark, spec in zip(found_bubbles, expected_bubbles):
        cx = (mark["left"] + mark["right"]) / 2.0
        cy = (mark["bottom"] + mark["top"]) / 2.0
        radius = (mark["right"] - mark["left"]) / 2.0
        px, py, pr = bubble_to_a4_pixels(cx, cy, radius)
        pages[mark["page"]]["bubbles"].append({
            **spec, "cx": cx, "cy": cy, "r": radius, "pixel": {"x": px, "y": py, "r": pr},
        })
    for mark, spec in zip(found_areas, expected_areas):
        if mark["kind"] != spec["type"]:
            raise ValueError(
                f"A área de escrita da questão {spec['number']} não corresponde ao tipo {spec['type']}."
            )
        x1, y1 = _pixels(mark["left"], mark["top"])
        x2, y2 = _pixels(mark["right"], mark["bottom"])
        pages[mark["page"]]["writing_areas"].append({
            **spec,
            "left": mark["left"], "bottom": mark["bottom"], "right": mark["right"], "top": mark["top"],
            "pixel": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
        })
    for mark, spec in zip(found_anchors, expected_anchors):
        cx = (mark["left"] + mark["right"]) / 2.0
        cy = (mark["bottom"] + mark["top"]) / 2.0
        px, py, _ = bubble_to_a4_pixels(cx, cy, 1.0)
        pages[mark["page"]]["row_anchors"].append({
            **spec, "cx": cx, "cy": cy, "pixel": {"x": px, "y": py},
        })

    return {
        "version": MAP_VERSION,
        "written_test_id": str(written_test_id),
        "page_count": len(page_contents),
        "units": "pt (origem no canto inferior esquerdo); pixel na A4 alinhada pelos quadrados",
        "pixel_space": {"width": A4_WIDTH_PX, "height": A4_HEIGHT_PX},
        "pages": [pages[n] for n in sorted(pages)],
    }


def extract_answer_sheet_map(pdf_bytes: bytes, items: List[Dict[str, Any]], written_test_id: str) -> Dict[str, Any]:
    from pypdf import PdfReader

    from app.socioeconomic_forms.services.answer_sheet_map import _page_content

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return build_answer_sheet_map_from_pages(
        [_page_content(page) for page in reader.pages], items, written_test_id
    )


# ---------------------------------------------------------------------------
# Alunos
# ---------------------------------------------------------------------------

def list_card_students(class_ids: List[str], student_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Alunos da turma atual de cada turma (inclui subturma ADAP). Escola e série vêm da turma."""
    from app.models.city import City
    from app.models.grades import Grade
    from app.models.school import School
    from app.models.student import Student
    from app.models.studentClass import Class

    uuids = [uuid.UUID(class_id) for class_id in class_ids]
    if not uuids:
        return []
    query = (
        db.session.query(
            Student.id, Student.name, Class.name, Grade.name, School.name, City.name, City.state,
        )
        .join(Class, Student.class_id == Class.id)
        .outerjoin(Grade, Class.grade_id == Grade.id)
        .outerjoin(School, School.id == Class._school_id)
        .outerjoin(City, School.city_id == City.id)
        .filter(Student.class_id.in_(uuids))
    )
    if student_id:
        query = query.filter(Student.id == str(student_id))
    query = query.order_by(School.name, Grade.name, Class.name, Student.name, Student.id)
    return [
        {
            "student_id": str(sid),
            "name": name or "",
            "class_name": class_name or "",
            "grade_name": grade_name or "",
            "school_name": school_name or "",
            "municipality": city_name or "",
            "state": state or "",
        }
        for sid, name, class_name, grade_name, school_name, city_name, state in query.all()
    ]


def applied_class_ids(written_test: ReadingWrittenTest) -> List[str]:
    return sorted({str(application.class_id) for application in (written_test.applications or [])})


def student_for_preview(written_test: ReadingWrittenTest, student_id: str) -> Dict[str, Any]:
    students = list_card_students(applied_class_ids(written_test), student_id=student_id)
    if not students:
        raise ValueError("O aluno não está numa turma aplicada desta avaliação.")
    return students[0]


# ---------------------------------------------------------------------------
# Registro da geração
# ---------------------------------------------------------------------------

def _overlaps(run: ReadingWrittenTestPrintRun, class_id: Optional[str]) -> bool:
    return run.class_id is None or class_id is None or str(run.class_id) == class_id


def find_active_run(written_test_id: str, class_id: Optional[str]) -> Optional[ReadingWrittenTestPrintRun]:
    now = _utcnow()
    runs = (
        ReadingWrittenTestPrintRun.query
        .filter(
            ReadingWrittenTestPrintRun.written_test_id == written_test_id,
            ReadingWrittenTestPrintRun.status.in_(ACTIVE_STATUSES),
        )
        .order_by(ReadingWrittenTestPrintRun.created_at.desc())
        .all()
    )
    for run in runs:
        reference = run.started_at or run.created_at
        if reference is not None and (now - reference) > timedelta(seconds=STALE_SECONDS):
            continue
        if _overlaps(run, class_id):
            return run
    return None


def create_run(user: Dict[str, Any], written_test_id: str, data: Optional[Dict[str, Any]]) -> ReadingWrittenTestPrintRun:
    written_test = WrittenTestService.get(written_test_id)
    build_card_items(written_test)

    applied = applied_class_ids(written_test)
    if not applied:
        raise ValueError("A avaliação ainda não foi aplicada a nenhuma turma.")

    raw = (data or {}).get("classId")
    class_id = None
    if raw not in (None, ""):
        class_id = _uuid_or_none(raw)
        if class_id is None:
            raise ValueError(f"classId inválido: {raw}")
        if class_id not in applied:
            raise ValueError(f"A turma {_class_label(class_id)} não está aplicada nesta avaliação.")

    active = find_active_run(written_test.id, class_id)
    if active is not None:
        raise GenerationInProgress(active)

    total = len(list_card_students([class_id] if class_id else applied))
    if total == 0:
        raise ValueError("Nenhum aluno nas turmas aplicadas.")

    run = ReadingWrittenTestPrintRun(
        written_test_id=written_test.id,
        class_id=uuid.UUID(class_id) if class_id else None,
        status=PRINT_RUN_PENDING,
        total_students=total,
        generated_count=0,
        created_by=_user_id(user),
        created_at=_utcnow(),
    )
    db.session.add(run)
    db.session.commit()
    return run


def dispatch_run(run: ReadingWrittenTestPrintRun, city_id: str) -> ReadingWrittenTestPrintRun:
    from app.afirme_ler.tasks import generate_written_test_answer_sheets

    try:
        task = generate_written_test_answer_sheets.delay(run.id, str(city_id))
    except Exception:
        run.status = PRINT_RUN_ERROR
        run.error_message = "Não foi possível enfileirar a geração."
        run.finished_at = _utcnow()
        db.session.commit()
        raise
    run.task_id = task.id
    db.session.commit()
    return run


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def run_to_dict(run: ReadingWrittenTestPrintRun, class_names: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    class_id = str(run.class_id) if run.class_id else None
    zip_available = run.status == PRINT_RUN_DONE and bool(run.minio_object_name)
    return {
        "id": run.id,
        "writtenTestId": run.written_test_id,
        "classId": class_id,
        "className": (class_names or {}).get(class_id) if class_id else None,
        "allClasses": class_id is None,
        "status": run.status,
        "taskId": run.task_id,
        "totalStudents": run.total_students or 0,
        "generatedCount": run.generated_count or 0,
        "errorMessage": run.error_message,
        "createdBy": run.created_by,
        "createdAt": _iso(run.created_at),
        "startedAt": _iso(run.started_at),
        "finishedAt": _iso(run.finished_at),
        "hasAnswerSheetMap": bool(run.answer_sheet_map) and "error" not in (run.answer_sheet_map or {}),
        "zipAvailable": zip_available,
        "downloadUrl": (
            f"/afirme-reading/written-tests/{run.written_test_id}/answer-sheets/{run.id}/download"
            if zip_available else None
        ),
    }


def _class_names(class_ids: List[str]) -> Dict[str, str]:
    from app.models.studentClass import Class

    uuids = [uuid.UUID(c) for c in class_ids if c]
    if not uuids:
        return {}
    return {str(k.id): k.name for k in Class.query.filter(Class.id.in_(uuids)).all()}


def describe_run(run: ReadingWrittenTestPrintRun) -> Dict[str, Any]:
    class_id = str(run.class_id) if run.class_id else None
    return run_to_dict(run, _class_names([class_id] if class_id else []))


def list_runs(written_test_id: str) -> Dict[str, Any]:
    written_test = WrittenTestService.get(written_test_id)
    runs = (
        ReadingWrittenTestPrintRun.query
        .filter(ReadingWrittenTestPrintRun.written_test_id == written_test.id)
        .order_by(ReadingWrittenTestPrintRun.created_at.desc(), ReadingWrittenTestPrintRun.id.asc())
        .all()
    )
    names = _class_names([str(run.class_id) for run in runs if run.class_id])
    return {"writtenTestId": written_test.id, "runs": [run_to_dict(run, names) for run in runs]}


def zip_object_name(written_test_id: str, run_id: str) -> str:
    return f"afirme-ler/written-tests/{written_test_id}/runs/{run_id}.zip"


def zip_download_name(written_test: ReadingWrittenTest, run: ReadingWrittenTestPrintRun) -> str:
    from app.services.cartao_resposta.answer_sheet_generator import sanitize_filename

    def safe(value: Optional[str], fallback: str) -> str:
        text = str(value or "")
        return sanitize_filename(text, max_length=50) if any(ch.isalnum() for ch in text) else fallback

    parts = ["cartoes", safe(written_test.title, "avaliacao")]
    if run.class_id:
        parts.append(safe(_class_names([str(run.class_id)]).get(str(run.class_id)), "turma"))
    return "_".join(parts) + ".zip"


def download_zip(written_test_id: str, run_id: str) -> Tuple[bytes, str]:
    from app.services.storage.minio_service import MinIOService

    written_test = WrittenTestService.get(written_test_id)
    run = ReadingWrittenTestPrintRun.query.filter_by(id=str(run_id), written_test_id=written_test.id).first()
    if run is None:
        raise LookupError("Geração de cartões não encontrada.")
    if run.status != PRINT_RUN_DONE:
        raise ValueError(f"A geração ainda não foi concluída (status: {run.status}).")
    if not run.minio_object_name:
        raise LookupError("ZIP dos cartões não encontrado.")
    data = MinIOService().download_file(
        run.minio_bucket or MinIOService.BUCKETS[BUCKET_KEY], run.minio_object_name
    )
    if not data:
        raise LookupError("ZIP dos cartões não encontrado no armazenamento.")
    return data, zip_download_name(written_test, run)


# ---------------------------------------------------------------------------
# Geração (chamada pela task Celery, já no schema do município)
# ---------------------------------------------------------------------------

def _mark_failed(run_id: str, message: str) -> None:
    db.session.rollback()
    run = db.session.get(ReadingWrittenTestPrintRun, run_id)
    if run is None:
        return
    run.status = PRINT_RUN_ERROR
    run.error_message = (message or "Falha ao gerar os cartões-resposta.")[:4000]
    run.finished_at = _utcnow()
    db.session.commit()


def run_generation(run_id: str, generator: Any = None) -> Dict[str, Any]:
    from pypdf import PdfReader

    from app.services.storage.minio_service import MinIOService
    from app.socioeconomic_forms.services.print_package import decide_print_outcome, write_print_zip

    run = db.session.get(ReadingWrittenTestPrintRun, run_id)
    if run is None:
        return {"success": False, "missing": True}
    if run.status not in ACTIVE_STATUSES:
        return {"success": False, "skipped": run.status}
    run.status = PRINT_RUN_PROCESSING
    run.started_at = _utcnow()
    db.session.commit()

    temp_dir = None
    try:
        written_test = WrittenTestService.get(run.written_test_id)
        items = build_card_items(written_test)
        class_ids = [str(run.class_id)] if run.class_id else applied_class_ids(written_test)
        students = list_card_students(class_ids)
        if not students:
            _mark_failed(run_id, "Nenhum aluno nas turmas aplicadas.")
            return {"success": False, "generated": 0}

        base_pdf = render_base_pdf(written_test, items, generator)
        page_count = len(PdfReader(io.BytesIO(base_pdf)).pages)
        map_error = None
        try:
            run.answer_sheet_map = extract_answer_sheet_map(base_pdf, items, written_test.id)
        except ValueError as exc:
            map_error = f"Mapa do cartão não extraído: {exc}"
            run.answer_sheet_map = {"version": MAP_VERSION, "error": str(exc)}
            logger.warning("[AFIRME-LER-CARD] run=%s %s", run_id, map_error)
        run.total_students = len(students)
        db.session.commit()

        title = written_test.title
        test_id = written_test.id

        def personalize(base: bytes, **student: Any) -> bytes:
            return personalize_answer_sheet_pdf(
                base,
                page_count=page_count,
                student_id=student.get("student_id") or "",
                written_test_id=test_id,
                title=title,
                student_name=student.get("student_name") or "",
                school_name=student.get("school_name") or "",
                grade_name=student.get("grade_name") or "",
                class_name=student.get("class_name") or "",
            )

        def on_progress(generated: int, failed: int, total: int) -> None:
            done = generated + failed
            if done != total and done % PROGRESS_EVERY != 0:
                return
            current = db.session.get(ReadingWrittenTestPrintRun, run_id)
            current.generated_count = generated
            db.session.commit()

        temp_dir = tempfile.mkdtemp(prefix="afirme_ler_cards_")
        zip_path = os.path.join(temp_dir, f"{run_id}.zip")
        stats = write_print_zip(
            zip_path, base_pdf, test_id, students, personalize=personalize, on_progress=on_progress
        )
        del base_pdf

        upload = None
        if stats["generated"] > 0:
            upload = MinIOService().upload_from_path(
                MinIOService.BUCKETS[BUCKET_KEY], zip_object_name(test_id, run_id), zip_path
            )
        outcome = decide_print_outcome(stats, upload)

        run = db.session.get(ReadingWrittenTestPrintRun, run_id)
        run.generated_count = stats["generated"]
        run.total_students = stats["total"]
        run.status = PRINT_RUN_DONE if outcome["status"] == "completed" else PRINT_RUN_ERROR
        if outcome.get("replace_zip"):
            run.minio_bucket = outcome.get("bucket")
            run.minio_object_name = outcome.get("object_name")
        errors = [message for message in (outcome.get("error"), map_error) if message]
        run.error_message = " | ".join(errors)[:4000] if errors else None
        run.finished_at = _utcnow()
        db.session.commit()
        logger.info(
            "[AFIRME-LER-CARD] run=%s status=%s gerados=%s falhas=%s",
            run_id, run.status, stats["generated"], stats["failed"],
        )
        return {"success": run.status == PRINT_RUN_DONE, "generated": stats["generated"], "failed": stats["failed"]}
    except Exception as exc:
        logger.error("[AFIRME-LER-CARD] Falha run=%s: %s", run_id, exc, exc_info=True)
        message = "Tempo esgotado ao gerar os cartões." if type(exc).__name__ == "SoftTimeLimitExceeded" else str(exc)
        _mark_failed(run_id, message)
        return {"success": False, "error": message}
    finally:
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
