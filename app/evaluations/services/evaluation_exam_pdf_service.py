# -*- coding: utf-8 -*-
"""PDF genérico da ficha da avaliação (capa + questões). Sem OMR e sem Celery."""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.decorators.tenant_required import get_current_tenant_context
from app.models.city import City
from app.exams.models.question import Question
from app.exams.models.test import Test
from app.exams.models.testQuestion import TestQuestion
from app.services.city_branding_service import apply_city_branding_to_test_data
from app.exams.services.institutional_test_weasyprint_generator import (
    InstitutionalTestWeasyPrintGenerator,
)
from app.utils.response_formatters import _get_all_subjects_from_test

logger = logging.getLogger(__name__)


class ExamPdfError(Exception):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR", status: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def exam_pdf_filename(title: str, include_gabarito: bool = False) -> str:
    """Nome do arquivo = título da avaliação (caracteres inseguros removidos)."""
    text = unicodedata.normalize("NFC", title or "").replace("\x00", "").strip()
    text = re.sub(r'[\\/:*?"<>|\r\n\t]', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        text = "avaliacao"
    text = text[:180].rstrip()
    if include_gabarito:
        return f"{text} - gabarito.pdf"
    return f"{text}.pdf"


class EvaluationExamPdfService:
    def build_exam_pdf(
        self,
        test_id: str,
        include_gabarito: bool = False,
    ) -> Tuple[bytes, str]:
        test = Test.query.get(test_id)
        if not test:
            raise ExamPdfError("Avaliação não encontrada", "NOT_FOUND", 404)

        questions_data = self._load_questions(test_id)
        if not questions_data:
            raise ExamPdfError("A avaliação não possui questões", "VALIDATION_ERROR", 400)

        test_data = self._build_test_data(test)
        generator = InstitutionalTestWeasyPrintGenerator()
        pdf_bytes = generator.generate_generic_evaluation_pdf(
            test_data,
            questions_data,
            include_gabarito=include_gabarito,
        )
        return pdf_bytes, exam_pdf_filename(test.title or "", include_gabarito)

    def _build_test_data(self, test: Test) -> Dict[str, Any]:
        grade_name = ""
        if getattr(test, "grade", None) is not None:
            grade_name = getattr(test.grade, "name", "") or ""
        test_data: Dict[str, Any] = {
            "id": test.id,
            "title": test.title,
            "description": test.description,
            "type": test.type,
            "model": getattr(test, "model", None),
            "grade_name": grade_name,
            "subjects_info": _get_all_subjects_from_test(test) or [],
        }
        city = self._current_city()
        if city:
            if getattr(city, "name", None):
                test_data.setdefault("municipality", city.name)
            if getattr(city, "state", None):
                test_data.setdefault("state", city.state)
        return apply_city_branding_to_test_data(test_data, city)

    def _current_city(self) -> Optional[City]:
        ctx = get_current_tenant_context()
        city_id = getattr(ctx, "city_id", None) if ctx else None
        if not city_id:
            return None
        return City.query.get(city_id)

    def _load_questions(self, test_id: str) -> List[Dict[str, Any]]:
        links = (
            TestQuestion.query.filter_by(test_id=test_id)
            .order_by(TestQuestion.order)
            .all()
        )
        question_ids = [link.question_id for link in links]
        if not question_ids:
            return []
        by_id = {q.id: q for q in Question.query.filter(Question.id.in_(question_ids)).all()}
        ordered: List[Dict[str, Any]] = []
        for link in links:
            question = by_id.get(link.question_id)
            if question:
                ordered.append(self._format_question(question, link.order))
        return ordered

    @staticmethod
    def _format_question(question: Question, order: Any) -> Dict[str, Any]:
        return {
            "id": question.id,
            "title": question.title,
            "text": question.text,
            "formatted_text": question.formatted_text,
            "secondstatement": question.secondstatement,
            "alternatives": question.alternatives or [],
            "correct_answer": question.correct_answer,
            "formatted_solution": question.formatted_solution,
            "question_type": question.question_type,
            "images": getattr(question, "images", None) or [],
            "subject_id": question.subject_id,
            "skill": question.skill,
            "order": order,
        }
