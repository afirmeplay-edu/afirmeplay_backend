# -*- coding: utf-8 -*-
"""
PDF BASE do questionário socioeconômico (documento de leitura humana).

Form → form.questions → contexto Jinja → socioeconomic_questionnaire.html → WeasyPrint.

O PDF BASE não tem dados de aluno. A capa traz o título do formulário e o
ano civil da execução (cover_year). Nome, escola, turma e QR ficam em branco
para o overlay de questionnaire_individual_pdf.py.
"""

import io
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from pypdf import PdfReader, PdfWriter

from app.services.institutional_test_weasyprint_generator import (
    InstitutionalTestWeasyPrintGenerator,
)

TEMPLATE_NAME = "socioeconomic_questionnaire.html"
ANSWER_SHEET_TEMPLATE = "socioeconomic_answer_sheet.html"
ANSWER_SHEET_START_KEY = "/SocioAnswerSheetStart"

# Só palavras bem curtas, sem espaço, substituem a letra na bolha (Não, Sim).
_SHORT_LABEL_MAX_CHARS = 4
_SHORT_LABEL_MAX_OPTIONS = 3

# Ano civil da capa. O fuso do processo (muitas vezes UTC) não vale:
# na virada do ano, UTC já pode estar no ano seguinte enquanto São Paulo não.
COVER_YEAR_TZ = ZoneInfo("America/Sao_Paulo")


def civil_cover_year(moment: Optional[datetime] = None) -> int:
    """Ano civil em America/Sao_Paulo. Calculado uma vez por PDF base.

    Não é a data de criação do formulário nem o carimbo de geração.
    Quem monta um pacote deve passar o mesmo valor para o único base
    da execução, em vez de recalcular por aluno.
    """
    if moment is None:
        current = datetime.now(COVER_YEAR_TZ)
    elif moment.tzinfo is None:
        current = moment.replace(tzinfo=COVER_YEAR_TZ)
    else:
        current = moment.astimezone(COVER_YEAR_TZ)
    return current.year

# Matrizes com mais linhas que isso podem quebrar entre páginas (entre linhas,
# nunca dentro de uma linha) para evitar grandes espaços em branco.
MATRIX_KEEP_TOGETHER_MAX_ROWS = 10

# Listas com mais opções que isso são exibidas em duas colunas.
OPTIONS_TWO_COLUMNS_MIN = 9


def _option_letter(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    letters = ""
    n = index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def _sub_question_letter(index: int) -> str:
    return _option_letter(index).lower()


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _layout_for(question: Any) -> str:
    """
    Layout pela forma real dos dados (não pelo nome do tipo):
    matriz_selecao, matriz_selecao_complexa e multipla_escolha armazenam
    options + sub_questions; selecao_unica só options; slider min/max.
    """
    options = _as_list(question.options)
    sub_questions = _as_list(question.sub_questions)
    if options and sub_questions:
        return "matrix"
    if options:
        return "options"
    if question.type == "slider" or question.min_value is not None or question.max_value is not None:
        return "number"
    return "text"


def _dependency_note(depends_on: Any, numbering: Dict[str, str]) -> Optional[Dict[str, Any]]:
    if not isinstance(depends_on, dict) or not depends_on.get("id"):
        return None
    reference = numbering.get(str(depends_on["id"]))
    if not reference:
        return None
    raw_value = depends_on.get("value")
    values = [str(v) for v in raw_value] if isinstance(raw_value, list) else (
        [str(raw_value)] if raw_value not in (None, "") else []
    )
    return {"reference": reference, "values": values}


class SocioeconomicQuestionnairePdfService:
    """Gera somente o PDF BASE (sem aluno, overlay, merge, Celery ou storage)."""

    def __init__(self, generator: Optional[InstitutionalTestWeasyPrintGenerator] = None):
        self._generator = generator or InstitutionalTestWeasyPrintGenerator()

    @staticmethod
    def build_questions(form_questions: List[Any]) -> List[Dict[str, Any]]:
        ordered = sorted(form_questions, key=lambda q: (q.question_order or 0))

        numbering: Dict[str, str] = {}
        for number, question in enumerate(ordered, 1):
            numbering[str(question.question_id)] = f"Questão {number}"
            for sub_index, sub in enumerate(_as_list(question.sub_questions)):
                if isinstance(sub, dict) and sub.get("id"):
                    numbering[str(sub["id"])] = (
                        f"Questão {number}, item {_sub_question_letter(sub_index)})"
                    )

        questions: List[Dict[str, Any]] = []
        for number, question in enumerate(ordered, 1):
            options = [str(o) for o in _as_list(question.options)]
            sub_questions = [
                {
                    "id": sub.get("id"),
                    "letter": _sub_question_letter(sub_index),
                    "text": sub.get("text") or "",
                }
                for sub_index, sub in enumerate(_as_list(question.sub_questions))
                if isinstance(sub, dict)
            ]
            layout = _layout_for(question)
            number_digits = len(str(question.max_value)) if question.max_value is not None else 3
            questions.append({
                "number": number,
                "id": question.question_id,
                "type": question.type,
                "layout": layout,
                "text": question.text or "",
                "options": [
                    {"letter": _option_letter(i), "text": text}
                    for i, text in enumerate(options)
                ],
                "options_two_columns": len(options) >= OPTIONS_TWO_COLUMNS_MIN,
                "sub_questions": sub_questions,
                "keep_together": layout != "matrix" or len(sub_questions) <= MATRIX_KEEP_TOGETHER_MAX_ROWS,
                "min_value": question.min_value,
                "max_value": question.max_value,
                "number_boxes": range(max(number_digits, 1)),
                "dependency": _dependency_note(question.depends_on, numbering),
            })
        return questions

    @staticmethod
    def build_card_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Blocos do cartão. Só entram perguntas de bolha; texto e número ficam no questionário."""
        cards = []
        for question in questions:
            if question.get("layout") not in ("options", "matrix"):
                continue
            options = question.get("options") or []
            short = (
                question.get("layout") == "matrix"
                and 0 < len(options) <= _SHORT_LABEL_MAX_OPTIONS
                and all(
                    " " not in option["text"] and len(option["text"]) <= _SHORT_LABEL_MAX_CHARS
                    for option in options
                )
            )
            cards.append({
                **question,
                "code": f"{int(question['number']):02d}",
                "short_labels": short,
                "legend": " | ".join(
                    f"{option['letter']}={option['text']}" for option in options
                ),
                "card_sub_questions": [
                    {**sub, "code": f"{question['number']}.{index}"}
                    for index, sub in enumerate(question.get("sub_questions") or [], 1)
                ],
            })
        return cards

    def build_context(self, form: Any, city: Any = None, cover_year: Optional[int] = None) -> Dict[str, Any]:
        title = (form.custom_title or form.title or "").strip()
        year = civil_cover_year() if cover_year is None else int(cover_year)
        questions = self.build_questions(list(form.questions))
        return {
            "form": {
                "id": form.id,
                "title": title,
                "description": (form.description or "").strip(),
                "instructions": (form.instructions or "").strip(),
            },
            "state": (getattr(city, "state", None) or "").strip(),
            "municipality": (getattr(city, "name", None) or "").strip(),
            "cover_year": year,
            "questions": questions,
            "card_questions": self.build_card_questions(questions),
            "default_logo": self._generator._load_default_logo(),
            # Metadado de auditoria. A frase da capa usa cover_year, não esta data.
            "generated_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }

    def render_html(self, form: Any, city: Any = None, cover_year: Optional[int] = None) -> str:
        return self._generator._render_template(
            TEMPLATE_NAME, self.build_context(form, city, cover_year)
        )

    def render_answer_sheet_html(self, form: Any, city: Any = None, cover_year: Optional[int] = None) -> str:
        return self._generator._render_template(
            ANSWER_SHEET_TEMPLATE, self.build_context(form, city, cover_year)
        )

    def generate_base_pdf(self, form: Any, city: Any = None, cover_year: Optional[int] = None) -> bytes:
        """Questionário de leitura e, no final, o cartão-resposta das bolhas."""
        context = self.build_context(form, city, cover_year)
        questionnaire = self._generator._html_to_pdf_bytes(
            self._generator._render_template(TEMPLATE_NAME, context)
        )
        if not context["card_questions"]:
            return questionnaire
        answer_sheet = self._generator._html_to_pdf_bytes(
            self._generator._render_template(ANSWER_SHEET_TEMPLATE, context)
        )
        return _append_pdf(questionnaire, answer_sheet)


def _append_pdf(first: bytes, second: bytes) -> bytes:
    first_reader = PdfReader(io.BytesIO(first))
    second_reader = PdfReader(io.BytesIO(second))
    writer = PdfWriter()
    for page in first_reader.pages:
        writer.add_page(page)
    for page in second_reader.pages:
        writer.add_page(page)
    writer.add_metadata({ANSWER_SHEET_START_KEY: str(len(first_reader.pages))})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
