# -*- coding: utf-8 -*-
"""
PDF individual do questionário socioeconômico.

O miolo vem de um PDF base já renderizado (WeasyPrint uma vez). Este módulo
desenha nome, escola, turma e o QR na capa, e repete os dados do aluno em
cada página do cartão-resposta que vai no final do PDF.

O QR identifica a folha para um leitor OMR futuro. O payload é curto, no
mesmo corte da prova física (12 primeiros caracteres de cada id):

    {"v": 1, "student_id": "<Student.id[:12]>", "form_id": "<Form.id[:12]>"}

Não chama o gerador de cartão nem o leitor existente. O leitor desta folha,
quando existir, precisa achar o Student.id e o Form.id do tenant cujo início
é exatamente esse prefixo. Zero ou mais de um resultado: recusar a gravação.
Não entregar este JSON ao leitor da prova física: ele procura test_id e usa
student_id como chave inteira.

Persistência das respostas — lacuna consciente, fora desta etapa
-----------------------------------------------------------------
FormResponse exige user_id e recipient_id, ambos NOT NULL, e é único em
(form_id, user_id). FormRecipient também exige user_id. Um aluno sem usuário
pode ser impresso e identificado pelo QR (Student.id + Form.id), mas o modelo
atual não tem onde gravar as marcas OMR dele.

Quando o leitor for implementado, a gravação precisa de um destino que aceite
Student.id sem user_id. Não criar FormRecipient artificial na geração do PDF.
Não alterar FormResponse nesta etapa. O leitor deve recusar a gravação se o
aluno estiver fora do escopo do formulário, em vez de cair no destinatário
virtual de outra pessoa.
"""

import io
import json
from typing import Any, Dict, Mapping, Optional

from pypdf import PdfReader, PdfWriter

QR_PAYLOAD_VERSION = 1
QR_ID_PREFIX_LENGTH = 12
ANSWER_SHEET_START_KEY = "/SocioAnswerSheetStart"

# Cabeçalho do cartão, em pt, origem no canto inferior esquerdo.
# Três colunas iguais na faixa de conteúdo (margem 1,15cm, QR de 1,7cm).
# O texto para na coluna: nome não entra na escola, escola não entra na turma.
_CARD_X_STUDENT = 36.0
_CARD_X_SCHOOL = 196.0
_CARD_X_CLASS = 357.0
_CARD_NAME_WIDTH = 152.0
_CARD_SCHOOL_WIDTH = 152.0
_CARD_CLASS_WIDTH = 148.0
_CARD_Y_VALUE = 788.0
# Mesma linha de base do rótulo "Nascimento:" no template (7pt).
_CARD_Y_META = 777.6
# Logo após os dois-pontos de "Nascimento:", medido no PDF base.
_CARD_X_BIRTH = 73.0
_CARD_QR_X = 512.0
_CARD_QR_Y = 762.0
_CARD_QR_SIZE = 46.0
# Centro da caixa "PÁGINA n DE m", com a linha de base no meio do retângulo.
_CARD_BADGE_X = 297.3
_CARD_BADGE_Y = 729.0

# Coordenadas em pt, origem no canto inferior esquerdo da página A4.
# Derivadas da capa deste questionário, não importadas do gerador da prova:
#   @page :first { margin-top: 1.2cm } e margens laterais de 2cm
#   .answer-sheet-header de 6,4cm, rótulo com min-width 100px, QR de 120px
# A caixa do QR inclui a borda (box-sizing: border-box). O desenho fica
# 2pt dentro dela para não cobrir a borda nem o rótulo "QR Code:".
_X_TEXT = 135.44
_Y_NAME = 780.16
_Y_SCHOOL = 744.31
_Y_CLASS = 732.36
_QR_BOX_X = 441.46
_QR_BOX_Y = 680.77
_QR_BOX_SIZE = 90.0
_QR_INSET = 2.0
_MAX_TEXT_CHARS = 50


def qr_id_prefix(value: str) -> str:
    """12 primeiros caracteres, o mesmo corte do QR da prova física."""
    return str(value or "").strip()[:QR_ID_PREFIX_LENGTH]


def build_qr_payload(student_id: str, form_id: str) -> Dict[str, Any]:
    """Identidade da folha. Prefixos de 12 caracteres, sem user_id."""
    student = qr_id_prefix(student_id)
    form = qr_id_prefix(form_id)
    if not student or not form:
        raise ValueError("student_id e form_id são obrigatórios no QR Code")
    return {
        "v": QR_PAYLOAD_VERSION,
        "student_id": student,
        "form_id": form,
    }


def qr_payload_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), separators=(",", ":"), ensure_ascii=False)


def build_qr_code(payload_text: str):
    """Símbolo do QR. Correção M cabe na versão 4 com os prefixos de 12 caracteres."""
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(payload_text)
    qr.make(fit=True)
    return qr


def _truncate(value: str, limit: int = _MAX_TEXT_CHARS) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def _fit_to_width(value: str, font: str, size: float, max_width: float) -> str:
    """Corta com '...' até a string caber na largura, em pt."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    text = (value or "").strip()
    if not text or stringWidth(text, font, size) <= max_width:
        return text
    ellipsis = "..."
    trimmed = text
    while trimmed and stringWidth(trimmed + ellipsis, font, size) > max_width:
        trimmed = trimmed[:-1]
    trimmed = trimmed.rstrip()
    return (trimmed + ellipsis) if trimmed else ellipsis


def _draw_fitted(canvas, text: str, x: float, y: float, max_width: float, font: str, size: float) -> None:
    """Desenha o texto inteiro, descendo a fonte até caber. Só corta se ainda passar."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    value = (text or "").strip()
    if not value:
        return
    chosen = size
    for candidate in (size, 7, 6.5, 6):
        if candidate > size:
            continue
        if stringWidth(value, font, candidate) <= max_width:
            chosen = candidate
            break
    else:
        value = _fit_to_width(value, font, 6, max_width)
        chosen = 6
    canvas.setFont(font, chosen)
    canvas.drawString(x, y, value)


def _class_line(grade_name: str, class_name: str) -> str:
    """A capa tem uma linha TURMA. Série e turma cabem nela."""
    grade = (grade_name or "").strip()
    class_label = (class_name or "").strip()
    if grade and class_label:
        return _truncate(f"{grade} - {class_label}")
    return _truncate(grade or class_label)


def render_cover_overlay_pdf(
    *,
    student_id: str,
    form_id: str,
    student_name: str = "",
    school_name: str = "",
    grade_name: str = "",
    class_name: str = "",
) -> bytes:
    """PDF A4 de uma página, só com os campos variáveis da capa."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    payload_text = qr_payload_text(build_qr_payload(student_id, form_id))
    qr = build_qr_code(payload_text)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = io.BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=A4)
    canvas.setFillColor(HexColor("#374151"))
    canvas.setFont("Helvetica", 7)

    name = _truncate(student_name).upper()
    school = _truncate(school_name).upper()
    class_line = _class_line(grade_name, class_name).upper()
    if name:
        canvas.drawString(_X_TEXT, _Y_NAME, name)
    if school:
        canvas.drawString(_X_TEXT, _Y_SCHOOL, school)
    if class_line:
        canvas.drawString(_X_TEXT, _Y_CLASS, class_line)

    draw_size = _QR_BOX_SIZE - (2 * _QR_INSET)
    canvas.drawImage(
        ImageReader(qr_buffer),
        _QR_BOX_X + _QR_INSET,
        _QR_BOX_Y + _QR_INSET,
        width=draw_size,
        height=draw_size,
        preserveAspectRatio=True,
        mask="auto",
    )
    canvas.save()
    buffer.seek(0)
    return buffer.read()


def answer_sheet_start_page(pdf_bytes: bytes) -> Optional[int]:
    """Índice da primeira página do cartão, gravado na geração do PDF base."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    raw = (reader.metadata or {}).get(ANSWER_SHEET_START_KEY)
    if raw in (None, ""):
        return None
    try:
        start = int(raw)
    except (TypeError, ValueError):
        return None
    if start < 0 or start >= len(reader.pages):
        return None
    return start


def _card_page_label(page_number: int, page_count: int) -> str:
    """Cada folha do cartão é uma página. Não há frente e verso."""
    return f"PÁGINA {page_number} DE {page_count}"


def _city_line(municipality: str, state: str) -> str:
    city = (municipality or "").strip()
    uf = (state or "").strip()
    if city and uf:
        return f"{city}/{uf}"
    return city or uf


def render_card_overlay_pdf(
    *,
    student_id: str,
    form_id: str,
    student_name: str = "",
    school_name: str = "",
    grade_name: str = "",
    class_name: str = "",
    birth_date: str = "",
    municipality: str = "",
    state: str = "",
    page_count: int = 1,
) -> bytes:
    """Um PDF com uma página de overlay por página do cartão. O QR é o mesmo em todas."""
    from reportlab.lib.colors import HexColor, black
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    payload_text = qr_payload_text(build_qr_payload(student_id, form_id))
    qr = build_qr_code(payload_text)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = io.BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_png = qr_buffer.getvalue()

    name = (student_name or "").strip().upper()
    school = (school_name or "").strip().upper()
    class_line = _class_line(grade_name, class_name).upper()
    city = _city_line(municipality, state).upper()
    born = (birth_date or "").strip()

    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=A4)
    for page_number in range(1, max(page_count, 1) + 1):
        canvas.setFillColor(HexColor("#111111"))
        _draw_fitted(
            canvas, name, _CARD_X_STUDENT, _CARD_Y_VALUE,
            _CARD_NAME_WIDTH, "Helvetica-Bold", 8,
        )
        _draw_fitted(
            canvas, school, _CARD_X_SCHOOL, _CARD_Y_VALUE,
            _CARD_SCHOOL_WIDTH, "Helvetica-Bold", 8,
        )
        canvas.setFillColor(HexColor("#111111"))
        if born:
            canvas.setFont("Helvetica", 7)
            canvas.drawString(_CARD_X_BIRTH, _CARD_Y_META, born)
        _draw_fitted(
            canvas, city, _CARD_X_SCHOOL, _CARD_Y_META,
            _CARD_SCHOOL_WIDTH, "Helvetica", 7,
        )
        _draw_fitted(
            canvas, class_line, _CARD_X_CLASS, _CARD_Y_META,
            _CARD_CLASS_WIDTH, "Helvetica", 7,
        )
        canvas.setFillColor(black)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawCentredString(
            _CARD_BADGE_X, _CARD_BADGE_Y, _card_page_label(page_number, page_count)
        )
        canvas.drawImage(
            ImageReader(io.BytesIO(qr_png)),
            _CARD_QR_X,
            _CARD_QR_Y,
            width=_CARD_QR_SIZE,
            height=_CARD_QR_SIZE,
            preserveAspectRatio=True,
            mask="auto",
        )
        canvas.showPage()
    canvas.save()
    buffer.seek(0)
    return buffer.read()


def apply_first_page_overlay(base_pdf: bytes, overlay_pdf: bytes) -> bytes:
    """Funde o overlay na página 1 e copia o restante do base.

    Cada chamada lê os bytes de novo. merge_page altera a página em memória;
    os bytes originais do base permanecem intactos para o próximo aluno.
    """
    if not base_pdf:
        raise ValueError("PDF base vazio")
    if not overlay_pdf:
        raise ValueError("Overlay vazio")

    base_reader = PdfReader(io.BytesIO(base_pdf))
    overlay_reader = PdfReader(io.BytesIO(overlay_pdf))
    if len(base_reader.pages) < 1:
        raise ValueError("PDF base sem páginas")
    if len(overlay_reader.pages) != 1:
        raise ValueError("O overlay da capa deve ter exatamente uma página")

    writer = PdfWriter()
    first_page = base_reader.pages[0]
    first_page.merge_page(overlay_reader.pages[0])
    writer.add_page(first_page)
    for page in base_reader.pages[1:]:
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def apply_card_overlays(base_pdf: bytes, overlay_pdf: bytes, start_page: int) -> bytes:
    """Funde cada página do overlay na página correspondente do cartão."""
    base_reader = PdfReader(io.BytesIO(base_pdf))
    writer = PdfWriter()
    if base_reader.metadata:
        writer.add_metadata({
            key: value
            for key, value in base_reader.metadata.items()
            if value is not None
        })
    for index, page in enumerate(base_reader.pages):
        slot = index - start_page
        if slot >= 0:
            layer = PdfReader(io.BytesIO(overlay_pdf))
            if slot < len(layer.pages):
                page.merge_page(layer.pages[slot])
        writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def personalize_questionnaire_pdf(
    base_pdf: bytes,
    *,
    student_id: str,
    form_id: str,
    student_name: str = "",
    school_name: str = "",
    grade_name: str = "",
    class_name: str = "",
    birth_date: str = "",
    municipality: str = "",
    state: str = "",
) -> bytes:
    """Um PDF completo do aluno. O HTML do questionário não é renderizado aqui."""
    cover = render_cover_overlay_pdf(
        student_id=student_id,
        form_id=form_id,
        student_name=student_name,
        school_name=school_name,
        grade_name=grade_name,
        class_name=class_name,
    )
    result = apply_first_page_overlay(base_pdf, cover)
    start = answer_sheet_start_page(base_pdf)
    if start is None:
        return result
    page_count = len(PdfReader(io.BytesIO(result)).pages) - start
    if page_count <= 0:
        return result
    card = render_card_overlay_pdf(
        student_id=student_id,
        form_id=form_id,
        student_name=student_name,
        school_name=school_name,
        grade_name=grade_name,
        class_name=class_name,
        birth_date=birth_date,
        municipality=municipality,
        state=state,
        page_count=page_count,
    )
    return apply_card_overlays(result, card, start)
