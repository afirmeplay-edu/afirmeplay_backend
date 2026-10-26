# -*- coding: utf-8 -*-
"""
PDF da prova (caderno de questões) da avaliação escrita do Afirme Ler.

build_pdf_data monta os dados só com o que pode ir para o papel (sem gabarito, isCorrect,
solução, pontuação nem palavra ditada) e não depende do WeasyPrint.
WrittenTestPdfService processa o HTML (imagens do MinIO em base64, fórmulas), renderiza
afirme_ler_written_test.html e gera os bytes com o InstitutionalTestWeasyPrintGenerator.
Gera na hora: não grava no MinIO nem no banco.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from markupsafe import Markup, escape

from app import db
from app.models.grades import Grade
from app.models.question import Question
from app.afirme_ler.models.reading_written_test import (
    WRITTEN_TEST_STATUS_PUBLISHED,
    ReadingWrittenTest,
)
from app.afirme_ler.services.question_bank_service import QUESTION_TYPE_MULTIPLE_CHOICE
from app.afirme_ler.services.written_test_service import _assert_allowed_type, _type_key

logger = logging.getLogger(__name__)

TEMPLATE_NAME = "afirme_ler_written_test.html"
ANSWER_ON_CARD = "Responda no cartão-resposta."


def _plain_to_html(text: Optional[str]) -> str:
    if not text or not str(text).strip():
        return ""
    lines = [str(escape(line)) for line in str(text).strip().splitlines()]
    return f"<p>{'<br>'.join(lines)}</p>"


def _statement_html(question: Question) -> str:
    formatted = question.formatted_text
    if formatted and str(formatted).strip():
        return str(formatted)
    return _plain_to_html(question.text)


def _parse_alternatives(raw: Any) -> List[Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    return raw if isinstance(raw, list) else []


def _alternative_html(question_id: str, alternative: Any) -> str:
    """Texto e/ou imagem da alternativa. isCorrect e demais campos não saem daqui."""
    if not isinstance(alternative, dict):
        return str(alternative or "")
    content = (
        alternative.get("formattedText")
        or alternative.get("text")
        or alternative.get("answer")
        or alternative.get("content")
        or ""
    )
    content = str(content)
    image = alternative.get("image")
    image_tag = ""
    if isinstance(image, dict) and image.get("id"):
        image_tag = f'<img src="/questions/{question_id}/images/{image["id"]}" />'
    elif isinstance(image, str) and image.startswith("data:image"):
        image_tag = f'<img src="{escape(image)}" />'
    return f"{content}{image_tag}" if content else image_tag


def _question_data(number: int, question: Question) -> Dict[str, Any]:
    question_type = _type_key(question.question_type)
    data = {
        "number": number,
        "id": question.id,
        "type": question_type,
        "statement_html": _statement_html(question),
        "images": list(question.images or []) if isinstance(question.images, list) else [],
    }
    if question_type == QUESTION_TYPE_MULTIPLE_CHOICE:
        data["support_html"] = question.secondstatement or ""
        data["alternatives"] = [
            {"letter": chr(65 + index), "content_html": _alternative_html(question.id, alt)}
            for index, alt in enumerate(_parse_alternatives(question.alternatives))
        ]
        data["answer_on_card"] = False
    else:
        data["support_html"] = ""
        data["alternatives"] = []
        data["answer_on_card"] = True
    return data


def build_pdf_data(written_test: ReadingWrittenTest, city: Any = None) -> Dict[str, Any]:
    """Dados da prova, na ordem da avaliação. Levanta ValueError se não puder gerar."""
    if written_test.status != WRITTEN_TEST_STATUS_PUBLISHED:
        raise ValueError("Só avaliação publicada pode gerar a prova.")

    links = sorted(written_test.questions or [], key=lambda link: link.order)
    ids = [link.question_id for link in links]
    found = {q.id: q for q in Question.query.filter(Question.id.in_(ids)).all()} if ids else {}

    questions = []
    for number, link in enumerate(links, start=1):
        question = found.get(link.question_id)
        if question is None:
            raise ValueError(
                f"A questão {link.question_id} (posição {link.order}) não existe mais no banco "
                "de questões. Não é possível gerar a prova."
            )
        _assert_allowed_type(question)
        questions.append(_question_data(number, question))

    grade_ids = [str(g) for g in (written_test.grade_ids or [])]
    grade_rows = (
        Grade.query.filter(Grade.id.in_([uuid.UUID(g) for g in grade_ids])).all()
        if grade_ids else []
    )
    grade_names = {str(row.id): row.name for row in grade_rows}
    grades = [grade_names[g] for g in grade_ids if grade_names.get(g)]

    return {
        "id": written_test.id,
        "title": written_test.title,
        "municipality": (getattr(city, "name", None) or "").strip(),
        "state": (getattr(city, "state", None) or "").strip(),
        "grades": grades,
        "grades_label": ", ".join(grades),
        "questions": questions,
        "total_questions": len(questions),
    }


def resolve_context_city() -> Any:
    """Município do contexto da requisição (token ou header do admin)."""
    from app.models.city import City
    from app.utils.tenant_middleware import get_current_tenant_context

    context = get_current_tenant_context()
    city_id = getattr(context, "city_id", None) if context else None
    return db.session.get(City, str(city_id)) if city_id else None


def pdf_filename(title: Optional[str]) -> str:
    from app.services.cartao_resposta.answer_sheet_generator import sanitize_filename

    text = str(title or "")
    safe = sanitize_filename(text, max_length=60) if any(ch.isalnum() for ch in text) else ""
    return f"prova_{safe or 'avaliacao'}.pdf"


class WrittenTestPdfService:
    def __init__(self, generator: Any = None):
        self._generator = generator

    @property
    def generator(self):
        if self._generator is None:
            from app.services.institutional_test_weasyprint_generator import (
                InstitutionalTestWeasyPrintGenerator,
            )

            self._generator = InstitutionalTestWeasyPrintGenerator()
        return self._generator

    def _html(self, raw: str, images: List[Any]) -> Markup:
        if not raw:
            return Markup("")
        from app.utils.render_math import render_math_in_html, render_math_in_text

        inlined = self.generator._inline_question_images_html(raw, images)
        with_math = render_math_in_html(inlined) if "<" in inlined else render_math_in_text(inlined)
        return self.generator._process_html_content(with_math)

    def _municipality_logo(self, city: Any) -> Optional[str]:
        if city is None or not getattr(city, "logo_url", None):
            return None
        try:
            from app.services.city_branding_service import CityBrandingService

            return CityBrandingService().build_test_data_branding_patch(city).get("municipality_logo")
        except Exception as exc:
            logger.warning("Afirme Ler PDF: logo do município indisponível: %s", exc)
            return None

    def build_template_context(self, data: Dict[str, Any], city: Any = None) -> Dict[str, Any]:
        questions = []
        for item in data["questions"]:
            images = item["images"]
            questions.append({
                "number": item["number"],
                "type": item["type"],
                "statement": self._html(item["statement_html"], images),
                "support": self._html(item["support_html"], images),
                "alternatives": [
                    {"letter": alt["letter"], "content": self._html(alt["content_html"], images)}
                    for alt in item["alternatives"]
                ],
                "answer_on_card": item["answer_on_card"],
            })
        return {
            "test": {
                "title": data["title"],
                "grades_label": data["grades_label"],
                "total_questions": data["total_questions"],
            },
            "municipality": data["municipality"],
            "state": data["state"],
            "questions": questions,
            "answer_on_card_text": ANSWER_ON_CARD,
            "municipality_logo": self._municipality_logo(city),
            "default_logo": self.generator._load_default_logo(),
        }

    def render_html(self, data: Dict[str, Any], city: Any = None) -> str:
        return self.generator._render_template(TEMPLATE_NAME, self.build_template_context(data, city))

    def generate_pdf(self, written_test: ReadingWrittenTest, city: Any = None) -> bytes:
        data = build_pdf_data(written_test, city)
        return self.generator._html_to_pdf_bytes(self.render_html(data, city))
