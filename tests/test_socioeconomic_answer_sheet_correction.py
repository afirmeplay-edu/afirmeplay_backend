# -*- coding: utf-8 -*-
"""Leitura do cartão socioeconômico, separada da correção da prova física."""
# Exec: python -m unittest tests.test_socioeconomic_answer_sheet_correction
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
_MAP = _ROOT / "app" / "socioeconomic_forms" / "services" / "answer_sheet_map.py"
_CORRECTION = _ROOT / "app" / "socioeconomic_forms" / "services" / "answer_sheet_correction.py"
_PDF = _ROOT / "app" / "socioeconomic_forms" / "services" / "questionnaire_pdf_service.py"
_INDIVIDUAL = _ROOT / "app" / "socioeconomic_forms" / "services" / "questionnaire_individual_pdf.py"

STUDENT_ID = "8f3c2a10-6b4e-4d77-9a21-0c5e7b91d4aa"
FORM_ID = "11aa22bb-33cc-44dd-55ee-66778899aabb"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


sheet_map = _load(_MAP, "socio_answer_sheet_map")
correction = _load(_CORRECTION, "socio_answer_sheet_correction")
pdf_service = _load(_PDF, "socio_questionnaire_pdf_service_for_correction")
individual = _load(_INDIVIDUAL, "socio_questionnaire_individual_for_correction")


def _question(question_id, order, text, qtype, options=None, sub_questions=None):
    return SimpleNamespace(
        question_id=question_id, question_order=order, text=text, type=qtype,
        options=options, sub_questions=sub_questions, min_value=None,
        max_value=None, depends_on=None,
    )


def _form():
    questions = [
        _question("q1", 1, "Qual é o seu gênero?", "selecao_unica",
                  options=["Feminino", "Masculino"]),
        _question("q2", 2, "Na rua onde você mora tem:", "matriz_selecao",
                  options=["Não", "Sim"],
                  sub_questions=[
                      {"id": "q2a", "text": "Água tratada?"},
                      {"id": "q2b", "text": "Iluminação?"},
                  ]),
    ]
    return SimpleNamespace(
        id=FORM_ID, title="Questionário", custom_title=None,
        description="", instructions="", questions=questions,
    )


class TestCardQrAndMerge(unittest.TestCase):
    def test_page_fraction_is_required(self):
        parsed = correction.parse_card_qr(
            '{"v":1,"student_id":"8f3c2a10-6b4","form_id":"11aa22bb-33c","p":"2/3"}'
        )
        self.assertEqual(parsed["page"], 2)
        self.assertEqual(parsed["page_count"], 3)
        self.assertIsNone(correction.parse_card_qr(
            '{"v":1,"student_id":"8f3c2a10-6b4","form_id":"11aa22bb-33c"}'
        ))
        self.assertIsNone(correction.parse_card_qr(
            '{"student_id":"8f3c2a10-6b4","test_id":"abc"}'
        ))

    def test_merge_keeps_sibling_matrix_answers(self):
        existing = {"q1": "Masculino", "q2a": "Não", "q2b": "Sim", "q3": "texto livre"}
        merged = correction.merge_marked_answers(existing, {"q2a": "Sim"})
        self.assertEqual(merged["q2a"], "Sim")
        self.assertEqual(merged["q2b"], "Sim")
        self.assertEqual(merged["q1"], "Masculino")
        self.assertEqual(merged["q3"], "texto livre")
        untouched = correction.merge_marked_answers(existing, {})
        self.assertEqual(untouched["q2b"], "Sim")

    def test_student_name_comes_from_the_student_record(self):
        self.assertEqual(
            correction.student_display_name(SimpleNamespace(name="  Maria Souza  ", user_id=None)),
            "Maria Souza",
        )
        self.assertIsNone(correction.student_display_name(SimpleNamespace(name="  ", user_id=None)))

    def test_payload_accepts_several_cards(self):
        documents = correction.payload_documents({
            "pdfs": ["pdf-a", "pdf-b"],
            "pdf": "pdf-c",
            "images": ["img-a", "img-b"],
        })
        self.assertEqual(
            [item["filename"] for item in documents],
            ["cartao.pdf", "cartao.pdf", "cartao.pdf", "cartao.png", "cartao.png"],
        )
        self.assertEqual([item["content"] for item in documents], ["pdf-a", "pdf-b", "pdf-c", "img-a", "img-b"])


class TestAnswerSheetMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.form = _form()
        cls.sheet = sheet_map.build_answer_sheet_map(cls.form)
        service = pdf_service.SocioeconomicQuestionnairePdfService()
        base = service.generate_base_pdf(cls.form)
        cls.personalized = individual.personalize_questionnaire_pdf(
            base, student_id=STUDENT_ID, form_id=FORM_ID, student_name="Aluno Teste",
        )

    def test_bubbles_follow_option_order(self):
        bubbles = [bubble for page in self.sheet["pages"] for bubble in page["bubbles"]]
        self.assertEqual(
            [(b["question_id"], b["letter"], b["text"]) for b in bubbles],
            [
                ("q1", "A", "Feminino"),
                ("q1", "B", "Masculino"),
                ("q2a", "A", "Não"),
                ("q2a", "B", "Sim"),
                ("q2b", "A", "Não"),
                ("q2b", "B", "Sim"),
            ],
        )
        self.assertGreaterEqual(self.sheet["page_count"], 1)
        for bubble in bubbles:
            self.assertGreater(bubble["cx"], 0)
            self.assertGreater(bubble["cy"], 0)
            self.assertGreater(bubble["r"], 2)

    def test_marked_bubble_becomes_the_option_text(self):
        images = correction.rasterize_pdf(self.personalized, dpi=200)
        card = images[-1]
        read = correction.read_card_image(card, self.sheet)
        self.assertEqual(read["status"], "read", read.get("reason"))
        self.assertEqual(read["qr"]["page"], 1)
        self.assertEqual(read["qr"]["student_id"], STUDENT_ID[:12])
        self.assertEqual(read["answers"], {})

        first = self.sheet["pages"][0]["bubbles"][0]
        x, y, radius = sheet_map.bubble_to_a4_pixels(first["cx"], first["cy"], first["r"])
        aligned = read["aligned"]
        self.assertEqual(aligned.shape[1], sheet_map.A4_WIDTH_PX)
        self.assertEqual(aligned.shape[0], sheet_map.A4_HEIGHT_PX)
        center = aligned[y, x]
        self.assertGreater(int(center.min()), 180)
        # O PNG da bolha não ocupa a caixa inteira de 12px; o traço fica um pouco dentro.
        ring_samples = [
            int(aligned[min(aligned.shape[0] - 1, y + offset), x].max())
            for offset in range(int(radius * 0.7), radius + 1)
        ]
        self.assertLess(min(ring_samples), 80)

        inner = max(2, int(round(radius * 0.65)))
        cv2.circle(aligned, (x, y), inner, (0, 0, 0), -1)
        answers, blank, invalid = correction.score_aligned_page(
            correction.SocioeconomicCardReader(), aligned, self.sheet["pages"][0]["bubbles"],
        )
        self.assertEqual(answers.get("q1"), "Feminino")
        self.assertNotIn("q1", blank)
        self.assertNotIn("q1", invalid)
        self.assertNotIn("q2a", answers)
        self.assertNotIn("q2b", answers)

        second = self.sheet["pages"][0]["bubbles"][1]
        sx, sy, sradius = sheet_map.bubble_to_a4_pixels(second["cx"], second["cy"], second["r"])
        cv2.circle(aligned, (sx, sy), max(2, int(round(sradius * 0.65))), (0, 0, 0), -1)
        answers, _blank, invalid = correction.score_aligned_page(
            correction.SocioeconomicCardReader(), aligned, self.sheet["pages"][0]["bubbles"],
        )
        self.assertNotIn("q1", answers)
        self.assertIn("q1", invalid)

    def test_several_files_stay_in_the_same_response(self):
        white = np.full((800, 600, 3), 255, dtype=np.uint8)
        result = correction.correct_uploaded_sheets(
            self.form,
            [white, white],
            sources=[
                {"fileIndex": 0, "pageIndex": 0, "filename": "aluno-a.pdf"},
                {"fileIndex": 1, "pageIndex": 0, "filename": "aluno-b.pdf"},
            ],
            load_errors=[{"fileIndex": 2, "filename": "ruim.pdf", "reason": "arquivo vazio"}],
            file_count=3,
        )
        self.assertEqual(result["fileCount"], 3)
        self.assertEqual(
            [(item["fileIndex"], item["filename"]) for item in result["skipped"]],
            [(0, "aluno-a.pdf"), (1, "aluno-b.pdf")],
        )
        self.assertEqual(result["errors"][0]["fileIndex"], 2)
        self.assertEqual(result["students"], [])


class TestUploadWithoutCard(unittest.TestCase):
    def test_plain_page_is_skipped(self):
        white = np.full((800, 600, 3), 255, dtype=np.uint8)
        sheet = {"form_id": FORM_ID, "page_count": 1, "pages": [{"page": 1, "bubbles": []}]}
        read = correction.read_card_image(white, sheet)
        self.assertEqual(read["status"], "skipped")
