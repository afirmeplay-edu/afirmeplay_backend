# -*- coding: utf-8 -*-
"""
PDF individual do questionário socioeconômico: overlay só na capa.

O miolo vem de um PDF base já renderizado (WeasyPrint uma vez). Este módulo
desenha nome, escola, turma e o QR Code na primeira página e copia as demais
sem novo HTML.

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
from typing import Any, Dict, Mapping

from pypdf import PdfReader, PdfWriter

QR_PAYLOAD_VERSION = 1
QR_ID_PREFIX_LENGTH = 12

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


def _truncate(value: str) -> str:
    text = (value or "").strip()
    if len(text) <= _MAX_TEXT_CHARS:
        return text
    return text[: _MAX_TEXT_CHARS - 1] + "…"


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


def personalize_questionnaire_pdf(
    base_pdf: bytes,
    *,
    student_id: str,
    form_id: str,
    student_name: str = "",
    school_name: str = "",
    grade_name: str = "",
    class_name: str = "",
) -> bytes:
    """Um PDF completo do aluno. O HTML do questionário não é renderizado aqui."""
    overlay = render_cover_overlay_pdf(
        student_id=student_id,
        form_id=form_id,
        student_name=student_name,
        school_name=school_name,
        grade_name=grade_name,
        class_name=class_name,
    )
    return apply_first_page_overlay(base_pdf, overlay)
