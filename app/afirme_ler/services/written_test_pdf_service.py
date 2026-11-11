# -*- coding: utf-8 -*-
"""
PDF da prova (caderno de questões) da avaliação escrita do Afirme Ler.

Layout visual alinhado à prova física institucional (capa Afirme, tipografia e
questões no padrão de institutional_test_hybrid.html). O cartão-resposta permanece
em PDF separado — não é embutido neste caderno.

mode=student: prova limpa.
mode=applicator: inclui ícones de megafone nos campos marcados (dictationMarks).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from markupsafe import Markup, escape

from app import db
from app.models.grades import Grade
from app.models.question import Question
from app.afirme_ler.models.reading_written_test import (
    WRITTEN_TEST_STATUS_PUBLISHED,
    ReadingWrittenTest,
)
from app.afirme_ler.services.question_bank_service import (
    QUESTION_TYPE_DICTATION,
    QUESTION_TYPE_MULTIPLE_CHOICE,
    QUESTION_TYPE_TEXT_PRODUCTION,
)
from app.afirme_ler.services.written_test_service import _assert_allowed_type, _type_key

logger = logging.getLogger(__name__)

TEMPLATE_NAME = "afirme_ler_written_test.html"
COVER_SUBJECT = "AVALIAÇÃO ESCRITA"
EDUCACIONAL_LOGO_FILENAME = "Afirme-edu-logo.png"
DICTATION_WRITING_LINES = 1
PRODUCTION_WRITING_LINES = 15
PDF_MODES = frozenset({"student", "applicator"})
MEGAPHONE_TOKEN = "__AFIRME_LER_MEGAPHONE__"
MEGAPHONE_SVG = (
    '<span class="dictation-icon" aria-label="Ler em voz alta">'
    '<svg viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="M3 10v4h4l5 4V6l-5 4H3zm12.5 2a3.5 3.5 0 0 0-2-3.16v6.32'
    "A3.5 3.5 0 0 0 15.5 12zm0-7.05v2.06a6 6 0 0 1 0 9.98v2.06a8 8 0 0 0 0-14.1z\"/>"
    "</svg></span>"
)
_EDUCACIONAL_LOGO_CACHE: Optional[str] = None


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


def _collect_image_metas(question: Question) -> List[Dict[str, Any]]:
    """Metadados MinIO do enunciado + alternativas (para inline no PDF)."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for image in question.images or [] if isinstance(question.images, list) else []:
        if isinstance(image, dict) and image.get("id"):
            by_id[str(image["id"])] = image
    for alternative in _parse_alternatives(question.alternatives):
        if not isinstance(alternative, dict):
            continue
        image = alternative.get("image")
        if isinstance(image, dict) and image.get("id"):
            image_id = str(image["id"])
            existing = by_id.get(image_id) or {}
            by_id[image_id] = {**existing, **image}
    return list(by_id.values())


def _alternative_image_tag(question_id: str, image: Any) -> str:
    if isinstance(image, str) and image.startswith("data:image"):
        return f'<img src="{escape(image)}" alt="" />'
    if not isinstance(image, dict):
        return ""
    image_id = image.get("id")
    if image_id:
        return f'<img src="/questions/{question_id}/images/{image_id}" alt="" />'
    image_url = image.get("imageUrl") or image.get("image_url") or image.get("url")
    if isinstance(image_url, str) and image_url.strip():
        return f'<img src="{escape(image_url.strip())}" alt="" />'
    raw = image.get("data") or image.get("base64")
    if isinstance(raw, str) and raw.strip():
        data = raw.strip()
        if not data.startswith("data:image"):
            mime = image.get("type") or "image/png"
            data = f"data:{mime};base64,{data}"
        return f'<img src="{escape(data)}" alt="" />'
    return ""


def _alternative_html(question_id: str, alternative: Any) -> str:
    """Texto e/ou imagem da alternativa. isCorrect e demais campos não saem daqui."""
    if not isinstance(alternative, dict):
        return str(alternative or "")
    content = (
        alternative.get("formattedText")
        or alternative.get("formatted_text")
        or alternative.get("text")
        or alternative.get("answer")
        or alternative.get("content")
        or ""
    )
    content = str(content)
    image_tag = _alternative_image_tag(question_id, alternative.get("image"))
    # Evita duplicar <img> se a figura já estiver no HTML da alternativa.
    if image_tag and image_tag in content:
        image_tag = ""
    elif image_tag and alternative.get("image") and isinstance(alternative.get("image"), dict):
        image_id = alternative["image"].get("id")
        if image_id and f"/images/{image_id}" in content:
            image_tag = ""
    return f"{content}{image_tag}" if content else image_tag


def _prepend_megaphone(html: str) -> str:
    """Coloca o megafone no início do primeiro parágrafo (inline), senão no começo."""
    if not html:
        return MEGAPHONE_TOKEN
    match = re.match(r"(<p\b[^>]*>)", html, flags=re.IGNORECASE)
    if match:
        return f"{html[:match.end()]}{MEGAPHONE_TOKEN}{html[match.end():]}"
    return f"{MEGAPHONE_TOKEN}{html}"


def _wrap_marked_images(html: str, image_ids: List[str]) -> str:
    """Envolve a <img> marcada com megafone ao lado — sem quebrar a tag."""
    text = html
    for image_id in image_ids:
        if not image_id:
            continue
        pattern = (
            r"(<img\b[^>]*\bsrc=[\"'][^\"']*"
            + re.escape(str(image_id))
            + r"[^\"']*[\"'][^>]*>)"
        )
        text = re.sub(
            pattern,
            rf'<span class="dictation-media">{MEGAPHONE_TOKEN}\1</span>',
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    return text


def normalize_pdf_mode(mode: Optional[str]) -> str:
    value = str(mode or "student").strip().lower() or "student"
    if value not in PDF_MODES:
        raise ValueError("mode inválido. Valores permitidos: student, applicator.")
    return value


def _effective_marks(link: Any, question: Question) -> Optional[Dict[str, Any]]:
    if getattr(link, "dictation_marks", None) is not None:
        return link.dictation_marks if isinstance(link.dictation_marks, dict) else None
    marks = question.dictation_marks
    return marks if isinstance(marks, dict) else None


def _writing_lines_for_type(question_type: str) -> int:
    if question_type == QUESTION_TYPE_DICTATION:
        return DICTATION_WRITING_LINES
    if question_type == QUESTION_TYPE_TEXT_PRODUCTION:
        return PRODUCTION_WRITING_LINES
    return 0


def _question_data(
    number: int,
    question: Question,
    dictation_marks: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    question_type = _type_key(question.question_type)
    writing_lines = _writing_lines_for_type(question_type)
    data = {
        "number": number,
        "id": question.id,
        "type": question_type,
        "title_html": _plain_to_html(question.title),
        "statement_html": _statement_html(question),
        "images": _collect_image_metas(question),
        "dictation_marks": dictation_marks if isinstance(dictation_marks, dict) else None,
        "writing_lines": writing_lines,
        # Múltipla escolha: marca no cartão separado. Ditado/bilhete: escreve nas linhas do caderno.
        "answer_on_card": question_type == QUESTION_TYPE_MULTIPLE_CHOICE,
    }
    if question_type == QUESTION_TYPE_MULTIPLE_CHOICE:
        data["support_html"] = question.secondstatement or ""
        data["alternatives"] = [
            {"letter": chr(65 + index), "content_html": _alternative_html(question.id, alt)}
            for index, alt in enumerate(_parse_alternatives(question.alternatives))
        ]
    else:
        data["support_html"] = ""
        data["alternatives"] = []
    return data


def build_pdf_data(
    written_test: ReadingWrittenTest,
    city: Any = None,
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Dados da prova, na ordem da avaliação. Levanta ValueError se não puder gerar."""
    if written_test.status != WRITTEN_TEST_STATUS_PUBLISHED:
        raise ValueError("Só avaliação publicada pode gerar a prova.")
    pdf_mode = normalize_pdf_mode(mode)

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
        marks = _effective_marks(link, question) if pdf_mode == "applicator" else None
        questions.append(_question_data(number, question, marks))

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
        "mode": pdf_mode,
    }


def resolve_context_city() -> Any:
    """Município do contexto da requisição (token ou header do admin)."""
    from app.models.city import City
    from app.utils.tenant_middleware import get_current_tenant_context

    context = get_current_tenant_context()
    city_id = getattr(context, "city_id", None) if context else None
    return db.session.get(City, str(city_id)) if city_id else None


def pdf_filename(title: Optional[str], mode: Optional[str] = None) -> str:
    from app.services.cartao_resposta.answer_sheet_generator import sanitize_filename

    text = str(title or "")
    safe = sanitize_filename(text, max_length=60) if any(ch.isalnum() for ch in text) else ""
    suffix = "_aplicador" if normalize_pdf_mode(mode) == "applicator" else ""
    return f"prova_{safe or 'avaliacao'}{suffix}.pdf"


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

    def _html(
        self,
        raw: str,
        images: List[Any],
        marked_image_ids: Optional[List[str]] = None,
    ) -> Markup:
        if not raw:
            return Markup("")
        from app.utils.render_math import render_math_in_html, render_math_in_text

        text = _wrap_marked_images(str(raw), list(marked_image_ids or []))
        inlined = self.generator._inline_question_images_html(text, images)
        with_math = render_math_in_html(inlined) if "<" in inlined else render_math_in_text(inlined)
        processed = self.generator._process_html_content(with_math)
        return Markup(str(processed).replace(MEGAPHONE_TOKEN, MEGAPHONE_SVG))

    def _municipality_logo(self, city: Any) -> Optional[str]:
        if city is None or not getattr(city, "logo_url", None):
            return None
        try:
            from app.services.city_branding_service import CityBrandingService

            return CityBrandingService().build_test_data_branding_patch(city).get("municipality_logo")
        except Exception as exc:
            logger.warning("Afirme Ler PDF: logo do município indisponível: %s", exc)
            return None

    def _educacional_logo(self) -> Optional[str]:
        """Logo Afirme Educacional (capa e fallback do cabeçalho do caderno)."""
        global _EDUCACIONAL_LOGO_CACHE
        if _EDUCACIONAL_LOGO_CACHE is not None:
            return _EDUCACIONAL_LOGO_CACHE or None
        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            EDUCACIONAL_LOGO_FILENAME,
        )
        try:
            if not os.path.exists(logo_path):
                logger.warning("Afirme Ler PDF: logo Educacional não encontrada em %s", logo_path)
                _EDUCACIONAL_LOGO_CACHE = ""
                return None
            with open(logo_path, "rb") as handle:
                _EDUCACIONAL_LOGO_CACHE = base64.b64encode(handle.read()).decode("utf-8")
            return _EDUCACIONAL_LOGO_CACHE
        except Exception as exc:
            logger.warning("Afirme Ler PDF: falha ao carregar logo Educacional: %s", exc)
            _EDUCACIONAL_LOGO_CACHE = ""
            return None

    def build_template_context(self, data: Dict[str, Any], city: Any = None) -> Dict[str, Any]:
        mode = data.get("mode") or "student"
        applicator_mode = mode == "applicator"
        questions = []
        for item in data["questions"]:
            images = item["images"]
            marks = item.get("dictation_marks") if applicator_mode else None
            marks = marks if isinstance(marks, dict) else {}
            # Índices de dictationMarks.images referem-se às figuras do enunciado (HTML),
            # não ao catálogo completo que também inclui alternativas.
            statement_image_ids = re.findall(
                r"/questions/[^/]+/images/([a-fA-F0-9-]{36})",
                item.get("statement_html") or "",
                flags=re.IGNORECASE,
            )
            marked_indexes = marks.get("images") or []
            marked_image_ids = []
            for index in marked_indexes:
                if isinstance(index, int) and 0 <= index < len(statement_image_ids):
                    marked_image_ids.append(statement_image_ids[index])

            title_html = item.get("title_html") or ""
            statement_html = item.get("statement_html") or ""
            support_html = item.get("support_html") or ""
            if applicator_mode and marks.get("title") and title_html:
                title_html = _prepend_megaphone(title_html)
            if applicator_mode and marks.get("statement") and statement_html:
                statement_html = _prepend_megaphone(statement_html)
            if applicator_mode and marks.get("support") and support_html:
                support_html = _prepend_megaphone(support_html)

            dictated_options = set(marks.get("options") or []) if applicator_mode else set()
            alternatives = []
            for alt in item["alternatives"]:
                content_html = alt["content_html"]
                if alt["letter"] in dictated_options:
                    content_html = _prepend_megaphone(content_html)
                alternatives.append({
                    "letter": alt["letter"],
                    "content": self._html(content_html, images),
                    "dictated": alt["letter"] in dictated_options,
                })

            writing_lines = int(item.get("writing_lines") or 0)
            questions.append({
                "number": item["number"],
                "type": item["type"],
                "title": self._html(title_html, images, marked_image_ids),
                "statement": self._html(statement_html, images, marked_image_ids),
                "support": self._html(support_html, images, marked_image_ids),
                "alternatives": alternatives,
                "answer_on_card": bool(item.get("answer_on_card")),
                "writing_lines": writing_lines,
                "dictation_marks": marks or None,
            })

        municipality_logo = self._municipality_logo(city)
        educacional_logo = self._educacional_logo()
        afirme_cover_base64, afirme_cover_mime = self.generator._load_afirme_cover_asset()
        grades = data.get("grades") or []
        grade_name = grades[0] if len(grades) == 1 else (data.get("grades_label") or "")
        return {
            "test": {
                "title": data["title"],
                "grades_label": data["grades_label"],
                "grade_name": grade_name,
                "total_questions": data["total_questions"],
            },
            "municipality": data["municipality"],
            "state": data["state"],
            "questions": questions,
            "mode": mode,
            "applicator_mode": applicator_mode,
            "municipality_logo": municipality_logo,
            "default_logo": educacional_logo,
            "educacional_logo": educacional_logo,
            "afirme_cover_base64": afirme_cover_base64,
            "afirme_cover_mime": afirme_cover_mime or "image/jpeg",
            "cover_subject": COVER_SUBJECT,
            "cover_year": datetime.now().year,
            "generated_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }

    def render_html(self, data: Dict[str, Any], city: Any = None) -> str:
        return self.generator._render_template(TEMPLATE_NAME, self.build_template_context(data, city))

    def generate_pdf(
        self,
        written_test: ReadingWrittenTest,
        city: Any = None,
        mode: Optional[str] = None,
    ) -> bytes:
        data = build_pdf_data(written_test, city, mode=mode)
        return self.generator._html_to_pdf_bytes(self.render_html(data, city))
