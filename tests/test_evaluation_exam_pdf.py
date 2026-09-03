# -*- coding: utf-8 -*-
"""Testes da ficha genérica da avaliação (sem OMR)."""
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pypdf import PdfReader

from app.services.evaluation_exam_pdf_service import exam_pdf_filename
from app.services.institutional_test_weasyprint_generator import (
    InstitutionalTestWeasyPrintGenerator,
)


class TestExamPdfHelpers(unittest.TestCase):
    def test_filename_is_evaluation_title(self):
        self.assertEqual(
            exam_pdf_filename("Avaliação Diagnóstica 5º Ano"),
            "Avaliação Diagnóstica 5º Ano.pdf",
        )

    def test_filename_without_gabarito(self):
        name = exam_pdf_filename("Avaliação Diagnóstica", include_gabarito=False)
        self.assertEqual(name, "Avaliação Diagnóstica.pdf")

    def test_filename_with_gabarito(self):
        self.assertEqual(
            exam_pdf_filename("Avaliação Diagnóstica", include_gabarito=True),
            "Avaliação Diagnóstica - gabarito.pdf",
        )

    def test_filename_strips_path_characters(self):
        self.assertEqual(exam_pdf_filename(r"A/B:C*D"), "A B C D.pdf")

    def test_filename_empty_fallback(self):
        self.assertEqual(exam_pdf_filename("   "), "avaliacao.pdf")


class TestFichaCoverFields(unittest.TestCase):
    def test_fields_override_keeps_only_three_keys(self):
        gen = InstitutionalTestWeasyPrintGenerator()
        template = SimpleNamespace(fields={
            "fields": [
                {"key": "aluno.nome", "x_norm": 0.1},
                {"key": "avaliacao.titulo", "x_norm": 0.2, "y_norm_from_top": 0.3},
                {"key": "disciplinas.nomes", "x_norm": 0.4},
                {"key": "escola.nome", "x_norm": 0.5},
                {"key": "serie.nome", "x_norm": 0.6},
            ]
        })
        override = gen._ficha_cover_fields_override(template)
        keys = [item["key"] for item in override["fields"]]
        self.assertEqual(keys, ["avaliacao.titulo", "disciplinas.nomes", "serie.nome"])
        self.assertEqual(override["fields"][0]["x_norm"], 0.2)


class TestExamSheetQuestionExtras(unittest.TestCase):
    def test_essay_without_alternatives(self):
        gen = InstitutionalTestWeasyPrintGenerator()
        question = {"question_type": "essay", "alternatives": []}
        gen._apply_exam_sheet_question_extras(question, include_gabarito=False)
        self.assertTrue(question["is_essay"])

    def test_gabarito_marks_correct_letter(self):
        gen = InstitutionalTestWeasyPrintGenerator()
        question = {
            "question_type": "multiple_choice",
            "correct_answer": "B",
            "alternatives": [
                {"letter": "A", "content": "um"},
                {"letter": "B", "content": "dois"},
            ],
        }
        gen._apply_exam_sheet_question_extras(question, include_gabarito=True)
        self.assertFalse(question["alternatives"][0]["is_correct"])
        self.assertTrue(question["alternatives"][1]["is_correct"])

    def test_without_gabarito_strips_answers(self):
        gen = InstitutionalTestWeasyPrintGenerator()
        question = {
            "correct_answer": "A",
            "formatted_solution": "<p>soma</p>",
            "alternatives": [{"letter": "A", "content": "1"}],
        }
        gen._apply_exam_sheet_question_extras(question, include_gabarito=False)
        self.assertNotIn("correct_answer", question)
        self.assertIsNone(question["solution"])
        self.assertFalse(question["alternatives"][0]["is_correct"])


class TestExamSheetTemplate(unittest.TestCase):
    def test_template_has_no_omr_markup(self):
        gen = InstitutionalTestWeasyPrintGenerator()
        html = gen._render_template(
            "evaluation_exam_sheet.html",
            {
                "test_data": {"title": "Prova"},
                "include_gabarito": False,
                "generated_date": "03/09/2026 16:00",
                "questions_by_subject": {
                    "Matemática": [{
                        "question_number": 1,
                        "skill_code": "",
                        "instruction": None,
                        "title": None,
                        "content": "<p>Quanto é 1+1?</p>",
                        "prompt": None,
                        "alternatives": [
                            {"letter": "A", "content": "1", "is_correct": False},
                            {"letter": "B", "content": "2", "is_correct": False},
                        ],
                        "is_essay": False,
                        "solution": None,
                    }]
                },
            },
        )
        self.assertIn("Questão 1", html)
        self.assertIn("Matemática", html)
        self.assertNotIn("answer-sheet", html)
        self.assertNotIn("QR Code", html)
        self.assertNotIn("BLOCO", html)
        self.assertNotIn("Aguarde instruções", html)

    def test_template_gabarito_and_essay(self):
        gen = InstitutionalTestWeasyPrintGenerator()
        html = gen._render_template(
            "evaluation_exam_sheet.html",
            {
                "test_data": {"title": "Prova"},
                "include_gabarito": True,
                "generated_date": "03/09/2026 16:00",
                "questions_by_subject": {
                    "Português": [{
                        "question_number": 1,
                        "skill_code": "",
                        "instruction": None,
                        "title": None,
                        "content": "<p>Redija.</p>",
                        "prompt": None,
                        "alternatives": [],
                        "is_essay": True,
                        "solution": "<p>Espera-se um parágrafo.</p>",
                    }]
                },
            },
        )
        self.assertIn("essay-box", html)
        self.assertIn("Resolução", html)


class TestGenericEvaluationPdfBuild(unittest.TestCase):
    def test_pdf_is_cover_plus_questions_without_omr(self):
        try:
            from weasyprint import HTML  # noqa: F401
        except ImportError:
            self.skipTest("weasyprint não disponível")

        gen = InstitutionalTestWeasyPrintGenerator()
        questions = [{
            "id": "q1",
            "formatted_text": "<p>Quanto é 2+2?</p>",
            "secondstatement": "",
            "alternatives": [
                {"id": "a", "text": "3"},
                {"id": "b", "text": "4"},
            ],
            "correct_answer": "B",
            "subject_id": "s1",
            "images": [],
            "question_type": "multiple_choice",
        }]
        test_data = {
            "id": "t1",
            "title": "Avaliação Diagnóstica",
            "grade_name": "5º Ano",
            "subjects_info": [{"id": "s1", "name": "Matemática"}],
        }

        with patch.object(gen, "_load_active_cover_template", return_value=(None, None)):
            pdf_bytes = gen.generate_generic_evaluation_pdf(
                test_data, questions, include_gabarito=False
            )

        reader = PdfReader(io.BytesIO(pdf_bytes))
        self.assertGreaterEqual(len(reader.pages), 2)
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        self.assertIn("Questão 1", text)
        self.assertNotIn("NOME COMPLETO", text)
        self.assertNotIn("QR Code", text)
        first = reader.pages[0]
        width = float(first.mediabox[2]) - float(first.mediabox[0])
        height = float(first.mediabox[3]) - float(first.mediabox[1])
        self.assertLess(abs(width - 595.27), 2.0)
        self.assertLess(abs(height - 841.89), 2.0)


if __name__ == "__main__":
    unittest.main()
