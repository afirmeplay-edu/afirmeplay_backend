# -*- coding: utf-8 -*-
"""
Mapa das bolhas do cartão socioeconômico.

O PDF base desenha cada bolha como um retângulo de 12px. A ordem desses
desenhos é a ordem do template: questão simples, depois cada linha da matriz,
e em cada linha as opções da esquerda para a direita. A letra A é a primeira
opção guardada na questão. O texto gravado no FormResponse é essa opção,
não a letra impressa.
"""

import io
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pypdf import PdfReader

# O gerador grava este metadado. Não passa pelo pacote services, que importa o app inteiro.
_ANSWER_SHEET_START_KEY = "/SocioAnswerSheetStart"

# Retângulo da bolha no fluxo do WeasyPrint, em px CSS, antes do cm da página.
_BUBBLE_CSS_PX = 12.0
_BUBBLE_TOLERANCE = 0.6

# A4 lógico da correção da prova física: os quadrados externos vão para os cantos.
A4_WIDTH_PX = 2480
A4_HEIGHT_PX = 3508
_ANCHOR_INSET_CM = 0.2
_PT_PER_CM = 72.0 / 2.54


def iter_card_bubbles(card_questions: List[Dict[str, Any]]):
    """Uma entrada por bolha, na ordem em que o template as desenha."""
    for question in card_questions:
        options = question.get("options") or []
        if question.get("layout") == "matrix":
            for sub in question.get("card_sub_questions") or []:
                for index, option in enumerate(options):
                    yield {
                        "question_id": sub.get("id"),
                        "parent_question_id": question.get("id"),
                        "code": sub.get("code"),
                        "letter": option.get("letter"),
                        "text": option.get("text"),
                        "option_index": index,
                    }
            continue
        for index, option in enumerate(options):
            yield {
                "question_id": question.get("id"),
                "parent_question_id": None,
                "code": question.get("code"),
                "letter": option.get("letter"),
                "text": option.get("text"),
                "option_index": index,
            }


def _multiply(ctm: Tuple[float, ...], matrix: Tuple[float, ...]) -> Tuple[float, ...]:
    """CTM novo = CTM atual × matriz do operador cm."""
    a1, b1, c1, d1, e1, f1 = ctm
    a2, b2, c2, d2, e2, f2 = matrix
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _apply(ctm: Tuple[float, ...], x: float, y: float) -> Tuple[float, float]:
    a, b, c, d, e, f = ctm
    return (a * x + c * y + e, b * x + d * y + f)


def _page_content(page) -> str:
    contents = page.get_contents()
    if contents is None:
        return ""
    streams = contents if isinstance(contents, list) else [contents]
    return b"\n".join(stream.get_data() for stream in streams).decode("latin1", errors="replace")


def _bubble_centers_from_content(content: str) -> List[Dict[str, float]]:
    """Centros em pontos PDF, origem no canto inferior esquerdo da página."""
    tokens = content.split()
    identity = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    ctm = identity
    stack = [identity]
    last_rect: Optional[Tuple[float, float, float, float]] = None
    centers: List[Dict[str, float]] = []
    number = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)$")

    for index, token in enumerate(tokens):
        if token == "q":
            stack.append(ctm)
        elif token == "Q" and len(stack) > 1:
            ctm = stack.pop()
        elif token == "cm" and index >= 6 and all(number.match(tokens[index - 6 + offset]) for offset in range(6)):
            matrix = tuple(float(tokens[index - 6 + offset]) for offset in range(6))
            ctm = _multiply(ctm, matrix)
        elif token == "re" and index >= 4 and all(number.match(tokens[index - 4 + offset]) for offset in range(4)):
            last_rect = tuple(float(tokens[index - 4 + offset]) for offset in range(4))
        elif token == "Do" and last_rect is not None:
            x, y, width, height = last_rect
            last_rect = None
            if abs(width - _BUBBLE_CSS_PX) > _BUBBLE_TOLERANCE or abs(height - _BUBBLE_CSS_PX) > _BUBBLE_TOLERANCE:
                continue
            left, bottom = _apply(ctm, x, y)
            right, top = _apply(ctm, x + width, y + height)
            centers.append({
                "cx": (left + right) / 2.0,
                "cy": (bottom + top) / 2.0,
                "r": abs(right - left) / 2.0,
            })
    return centers


def _pdf_service():
    qualified = "app.socioeconomic_forms.services.questionnaire_pdf_service"
    loaded = sys.modules.get(qualified)
    if loaded is not None:
        return loaded
    path = Path(__file__).with_name("questionnaire_pdf_service.py")
    spec = importlib.util.spec_from_file_location("_socio_questionnaire_pdf_service", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _answer_sheet_start(reader: PdfReader) -> Optional[int]:
    raw = (reader.metadata or {}).get(_ANSWER_SHEET_START_KEY)
    if raw in (None, ""):
        return None
    try:
        start = int(raw)
    except (TypeError, ValueError):
        return None
    if start < 0 or start >= len(reader.pages):
        return None
    return start


def build_answer_sheet_map(form: Any, city: Any = None, cover_year: Optional[int] = None) -> Dict[str, Any]:
    """Mapa do formulário a partir do mesmo PDF base que vai para a impressão."""
    service = _pdf_service().SocioeconomicQuestionnairePdfService()
    context = service.build_context(form, city, cover_year)
    expected = list(iter_card_bubbles(context["card_questions"]))
    if not expected:
        return {"form_id": str(form.id), "page_count": 0, "pages": []}

    pdf_bytes = service.generate_base_pdf(form, city, cover_year)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    start = _answer_sheet_start(reader)
    if start is None:
        raise ValueError("PDF do cartão sem a página inicial das bolhas")

    found: List[Dict[str, float]] = []
    page_breaks = [0]
    for page in reader.pages[start:]:
        found.extend(_bubble_centers_from_content(_page_content(page)))
        page_breaks.append(len(found))

    if len(found) != len(expected):
        raise ValueError(
            f"O cartão desenhou {len(found)} bolhas e o formulário tem {len(expected)}"
        )

    pages = []
    for page_number, (begin, end) in enumerate(zip(page_breaks, page_breaks[1:]), 1):
        bubbles = []
        for center, spec in zip(found[begin:end], expected[begin:end]):
            bubbles.append({**spec, **center, "page": page_number})
        pages.append({"page": page_number, "bubbles": bubbles})

    return {
        "form_id": str(form.id),
        "page_count": len(pages),
        "pages": pages,
    }


def bubble_to_a4_pixels(
    cx: float,
    cy: float,
    radius: float,
    page_width: float = 595.275591,
    page_height: float = 841.889764,
) -> Tuple[int, int, int]:
    """Ponto PDF → pixel da A4 alinhada pelos quadrados externos.

    O warp da prova física manda o vértice externo de cada quadrado para o
    canto da imagem. Esse vértice fica a 0,2 cm da borda da folha.
    """
    inset = _ANCHOR_INSET_CM * _PT_PER_CM
    span_x = page_width - (2.0 * inset)
    span_y = page_height - (2.0 * inset)
    image_x = (cx - inset) / span_x * A4_WIDTH_PX
    image_y = ((page_height - inset) - cy) / span_y * A4_HEIGHT_PX
    image_r = radius / span_x * A4_WIDTH_PX
    return int(round(image_x)), int(round(image_y)), max(2, int(round(image_r)))
