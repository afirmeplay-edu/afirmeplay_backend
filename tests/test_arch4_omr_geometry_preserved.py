# -*- coding: utf-8 -*-
"""
Garante que a otimização de imagens das questões não altera o OMR.

O cartão-resposta é renderizado com include_answer_sheet=True e
include_questions=False — question.content não entra no HTML do cartão.
"""
import base64
import hashlib
import inspect
import io
import os
import re
import unittest

import numpy as np
from PIL import Image
from pypdf import PdfReader

from app.services.cartao_resposta.correction_new_grid import AnswerSheetCorrectionNewGrid
from app.services.institutional_test_weasyprint_generator import (
    InstitutionalTestWeasyPrintGenerator,
)
from app.utils.pdf_question_image_optimizer import optimize_html_data_uris


A4_WIDTH_PT = 595.27
A4_HEIGHT_PT = 841.89
A4_TOLERANCE_PT = 1.0

_REPO = os.path.dirname(os.path.dirname(__file__))
GENERATOR_PATH = os.path.join(_REPO, "app", "services", "institutional_test_weasyprint_generator.py")
TEMPLATE_PATH = os.path.join(_REPO, "app", "templates", "institutional_test_hybrid.html")
CORRECTOR_PATH = os.path.join(_REPO, "app", "services", "cartao_resposta", "correction_new_grid.py")


def _huge_question_content() -> str:
    rng = np.random.default_rng(9)
    arr = rng.integers(0, 256, size=(1800, 1800, 3), dtype="uint8")
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return (
        f'<p>Enunciado com imagem</p>'
        f'<img src="data:image/jpeg;base64,{b64}" alt="fig" />'
    )


def _omr_template_data(question_content: str, generated_date: str = "01/01/2026 00:00"):
    questions_by_subject = {
        "Matemática": [
            {
                "question_number": 1,
                "content": question_content,
                "prompt": None,
                "alternatives": [
                    {"letter": "A", "content": "alt A"},
                    {"letter": "B", "content": "alt B"},
                    {"letter": "C", "content": "alt C"},
                    {"letter": "D", "content": "alt D"},
                ],
                "skill_code": "",
            }
        ]
    }
    gen = InstitutionalTestWeasyPrintGenerator()
    return {
        "test_data": {"title": "Prova OMR Isolada", "state": "ALAGOAS", "grade_name": "9º ANO"},
        "student": {
            "name": "",
            "school_name": "",
            "class_name": "",
            "qr_code": gen._get_omr_placeholder_qr_base64(),
        },
        "questions_by_subject": questions_by_subject,
        "questions_by_block": None,
        "blocks_config": {"use_blocks": False},
        "questions_map": {1: ["A", "B", "C", "D"]},
        "answer_sheet_image": "",
        "total_questions": 1,
        "generated_date": generated_date,
        "default_logo": None,
        "include_cover": False,
        "include_questions": False,
        "include_answer_sheet": True,
    }, gen


def _pdf_geometry(pdf_bytes: bytes) -> dict:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page = reader.pages[0]
    mediabox = [float(x) for x in page.mediabox]
    cropbox = [float(x) for x in page.cropbox]
    rotate = int(page.get("/Rotate", 0) or 0)
    contents = page.get_contents()
    content_data = contents.get_data() if contents is not None else b""
    return {
        "pages": len(reader.pages),
        "mediabox": mediabox,
        "cropbox": cropbox,
        "rotation": rotate,
        "contents_sha256": hashlib.sha256(content_data).hexdigest(),
        "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
    }


def _assert_a4(test: unittest.TestCase, geom: dict) -> None:
    width = geom["mediabox"][2] - geom["mediabox"][0]
    height = geom["mediabox"][3] - geom["mediabox"][1]
    test.assertEqual(geom["pages"], 1)
    test.assertEqual(geom["rotation"], 0)
    test.assertLess(abs(width - A4_WIDTH_PT), A4_TOLERANCE_PT)
    test.assertLess(abs(height - A4_HEIGHT_PT), A4_TOLERANCE_PT)
    crop_w = geom["cropbox"][2] - geom["cropbox"][0]
    crop_h = geom["cropbox"][3] - geom["cropbox"][1]
    test.assertLess(abs(crop_w - A4_WIDTH_PT), A4_TOLERANCE_PT)
    test.assertLess(abs(crop_h - A4_HEIGHT_PT), A4_TOLERANCE_PT)


class TestArch4OmrGeometryPreserved(unittest.TestCase):
    def test_omr_html_ignores_question_image_payload(self):
        huge = _huge_question_content()
        optimized = optimize_html_data_uris(huge)
        self.assertNotEqual(optimized, huge)

        data_orig, gen = _omr_template_data(huge)
        data_opt, _ = _omr_template_data(optimized)

        html_orig = gen._render_template("institutional_test_hybrid.html", data_orig)
        html_opt = gen._render_template("institutional_test_hybrid.html", data_opt)

        self.assertNotIn("data:image/jpeg", html_orig)
        self.assertNotIn("data:image/jpeg", html_opt)
        self.assertEqual(html_orig, html_opt)
        self.assertIn("answer-sheet", html_orig)
        self.assertIn("bubble", html_orig)
        self.assertNotIn("Enunciado com imagem", html_orig)

    def test_omr_pdf_geometry_unchanged_when_question_images_change(self):
        try:
            from weasyprint import HTML  # noqa: F401
        except ImportError:
            self.skipTest("weasyprint não disponível")

        huge = _huge_question_content()
        optimized = optimize_html_data_uris(huge)
        data_orig, gen = _omr_template_data(huge)
        data_opt, _ = _omr_template_data(optimized)

        pdf_orig = gen._html_to_pdf_bytes(
            gen._render_template("institutional_test_hybrid.html", data_orig)
        )
        pdf_opt = gen._html_to_pdf_bytes(
            gen._render_template("institutional_test_hybrid.html", data_opt)
        )

        geom_orig = _pdf_geometry(pdf_orig)
        geom_opt = _pdf_geometry(pdf_opt)
        _assert_a4(self, geom_orig)
        _assert_a4(self, geom_opt)
        self.assertEqual(geom_orig["pages"], geom_opt["pages"])
        self.assertEqual(geom_orig["mediabox"], geom_opt["mediabox"])
        self.assertEqual(geom_orig["cropbox"], geom_opt["cropbox"])
        self.assertEqual(geom_orig["rotation"], geom_opt["rotation"])
        self.assertEqual(geom_orig["contents_sha256"], geom_opt["contents_sha256"])

    def test_html_to_pdf_bytes_has_no_extra_weasyprint_params(self):
        sig = inspect.signature(InstitutionalTestWeasyPrintGenerator._html_to_pdf_bytes)
        self.assertEqual(list(sig.parameters), ["self", "html_content"])

    def test_overlay_coordinates_untouched_in_source(self):
        with open(GENERATOR_PATH, encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn("X_TEXT = 135.44", source)
        self.assertIn("Y_PDF_NAME   = 780.16", source)
        self.assertIn("QR_X = 441.46", source)
        self.assertIn("QR_SIZE = 90", source)
        self.assertIn("def _generate_student_overlay_pdf", source)
        self.assertIn("def _map_existing_form_coordinates", source)

    def test_omr_css_geometry_untouched_in_template(self):
        with open(TEMPLATE_PATH, encoding="utf-8") as fh:
            css = fh.read()
        self.assertIn("@page answer-sheet-omr", css)
        self.assertIn("margin: 0;", css)
        self.assertIn(".answer-sheet {", css)
        self.assertIn("width: 21cm;", css)
        self.assertIn("height: 29.7cm;", css)
        self.assertIn("padding: 1.2cm 2cm 2.2cm 2cm;", css)
        self.assertIn(
            'background-image: url("data:image/png;base64,{{ test_data.letterhead_image_base64 }}");',
            css,
        )
        self.assertRegex(css, r"\.bubble\s*\{[^}]*width:\s*15px")
        self.assertRegex(css, r"\.bubble\s*\{[^}]*height:\s*15px")

    def test_corrector_constants_untouched(self):
        omr = AnswerSheetCorrectionNewGrid(debug=False)
        self.assertEqual(omr.ROW_HEIGHT_PX, 51.97)
        self.assertEqual(omr.BUBBLE_RADIUS_PX, 25)
        self.assertEqual(omr.BUBBLE_SPACING_PX, 61)
        self.assertEqual(omr.BLOCK_OFFSET_X, 115)
        self.assertEqual(omr.BLOCK_OFFSET_Y, 40)
        self.assertEqual(omr.A4_WIDTH_PX, 2480)
        self.assertEqual(omr.A4_HEIGHT_PX, 3508)
        with open(CORRECTOR_PATH, encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("optimize_question_image", source)
        self.assertNotIn("pdf_question_image_optimizer", source)

    def test_optimize_method_does_not_touch_questions_map(self):
        gen = InstitutionalTestWeasyPrintGenerator()
        questions_map = {1: ["A", "B", "C", "D"]}
        questions_by_subject = {
            "Matemática": [
                {
                    "question_number": 1,
                    "content": _huge_question_content(),
                    "alternatives": [{"letter": "A", "content": "x"}],
                }
            ]
        }
        gen._optimize_question_images_for_questions_pdf(questions_by_subject, None)
        self.assertEqual(questions_map, {1: ["A", "B", "C", "D"]})
        self.assertEqual(questions_by_subject["Matemática"][0]["question_number"], 1)
        self.assertEqual(questions_by_subject["Matemática"][0]["alternatives"][0]["letter"], "A")


if __name__ == "__main__":
    unittest.main()
