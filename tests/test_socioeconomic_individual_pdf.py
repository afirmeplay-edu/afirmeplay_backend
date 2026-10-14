# -*- coding: utf-8 -*-
"""PDF individual: QR na capa e miolo igual ao base."""
# Exec: python -m unittest tests.test_socioeconomic_individual_pdf
import importlib.util
import io
import json
import unittest
from pathlib import Path

from pypdf import PdfReader

_MODULE = (
    Path(__file__).resolve().parents[1]
    / "app" / "socioeconomic_forms" / "services" / "questionnaire_individual_pdf.py"
)
_PDF_SERVICE = (
    Path(__file__).resolve().parents[1]
    / "app" / "socioeconomic_forms" / "services" / "questionnaire_pdf_service.py"
)

STUDENT_ID = "8f3c2a10-6b4e-4d77-9a21-0c5e7b91d4aa"
FORM_ID = "11aa22bb-33cc-44dd-55ee-66778899aabb"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


individual = _load(_MODULE, "socio_questionnaire_individual_pdf")
pdf_service = _load(_PDF_SERVICE, "socio_questionnaire_pdf_service_for_individual")


def _question(question_id, order, text, qtype, options=None, sub_questions=None,
              min_value=None, max_value=None, depends_on=None):
    from types import SimpleNamespace
    return SimpleNamespace(
        question_id=question_id, question_order=order, text=text, type=qtype,
        options=options, sub_questions=sub_questions, min_value=min_value,
        max_value=max_value, depends_on=depends_on,
    )


def _form():
    from types import SimpleNamespace
    questions = [
        _question("q1", 1, "Qual é o seu gênero?", "selecao_unica",
                  options=["Feminino", "Masculino"]),
        _question("q2", 2, "Na rua onde você mora tem:", "matriz_selecao",
                  options=["Não", "Sim"],
                  sub_questions=[{"id": "q2a", "text": "Água tratada?"}]),
    ]
    return SimpleNamespace(
        id=FORM_ID, title="Questionário de sistema", custom_title="Avaliação Municipal",
        description="Anos finais", instructions="", questions=questions,
    )


class TestQrPayload(unittest.TestCase):
    def test_payload_uses_twelve_character_prefixes(self):
        payload = individual.build_qr_payload(STUDENT_ID, FORM_ID)
        self.assertEqual(payload, {
            "v": 1,
            "student_id": STUDENT_ID[:12],
            "form_id": FORM_ID[:12],
        })
        encoded = individual.qr_payload_text(payload)
        self.assertEqual(json.loads(encoded)["student_id"], "8f3c2a10-6b4")
        self.assertEqual(json.loads(encoded)["form_id"], "11aa22bb-33c")
        self.assertLessEqual(len(encoded.encode("utf-8")), 62)
        self.assertNotIn("user_id", encoded)
        self.assertNotIn("test_id", encoded)
        symbol = individual.build_qr_code(encoded)
        self.assertEqual(symbol.version, 4)

    def test_card_payload_carries_the_page_fraction(self):
        payload = individual.build_qr_payload(STUDENT_ID, FORM_ID, page=2, page_count=3)
        self.assertEqual(payload["p"], "2/3")
        self.assertEqual(payload["student_id"], STUDENT_ID[:12])
        encoded = individual.qr_payload_text(payload)
        self.assertIn('"p":"2/3"', encoded)
        symbol = individual.build_qr_code(encoded)
        self.assertGreaterEqual(symbol.version, 4)
        with self.assertRaises(ValueError):
            individual.build_qr_payload(STUDENT_ID, FORM_ID, page=4, page_count=3)
        with self.assertRaises(ValueError):
            individual.build_qr_payload(STUDENT_ID, FORM_ID, page=1)

    def test_payload_rejects_blank_ids(self):
        with self.assertRaises(ValueError):
            individual.build_qr_payload("", FORM_ID)
        with self.assertRaises(ValueError):
            individual.build_qr_payload(STUDENT_ID, "  ")


class TestCardHeaderFit(unittest.TestCase):
    def test_long_name_and_school_stay_in_their_columns(self):
        from reportlab.pdfbase.pdfmetrics import stringWidth

        overlay = individual.render_card_overlay_pdf(
            student_id=STUDENT_ID,
            form_id=FORM_ID,
            student_name="Adryann Luciano de Oliveira da Silva",
            school_name="Colégio Municipal Esther Soares Torres",
            grade_name="4º Ano",
            class_name="Turma A",
            birth_date="29/05/2016",
            municipality="São Miguel dos Campos",
            state="AL",
        )
        placed = []

        def visitor(text, _cm, tm, font_dict, font_size):
            if text and text.strip():
                placed.append((text, tm[4], font_size, font_dict.get("/BaseFont", "")))

        PdfReader(io.BytesIO(overlay)).pages[0].extract_text(visitor_text=visitor)
        name = next(item for item in placed if item[0].startswith("ADRYANN"))
        school = next(item for item in placed if item[0].startswith("COL"))
        self.assertLessEqual(
            name[1] + stringWidth(name[0], "Helvetica-Bold", name[2]),
            individual._CARD_X_SCHOOL - 4,
        )
        self.assertLessEqual(
            school[1] + stringWidth(school[0], "Helvetica-Bold", school[2]),
            individual._CARD_X_CLASS - 4,
        )
        self.assertIn("ADRYANN LUCIANO DE OLIVEIRA DA SILVA", name[0])
        self.assertIn("COLÉGIO MUNICIPAL ESTHER SOARES TORRES", school[0])


class TestIndividualPdf(unittest.TestCase):
    def test_cover_is_personal_and_inner_pages_match_the_base(self):
        try:
            from weasyprint import HTML  # noqa: F401
        except ImportError:
            self.skipTest("weasyprint não disponível")

        base = pdf_service.SocioeconomicQuestionnairePdfService().generate_base_pdf(
            _form(), cover_year=2026
        )
        personalized = individual.personalize_questionnaire_pdf(
            base,
            student_id=STUDENT_ID,
            form_id=FORM_ID,
            student_name="Maria da Silva",
            school_name="Escola João XXIII",
            grade_name="9º Ano",
            class_name="Turma B",
        )
        base_reader = PdfReader(io.BytesIO(base))
        reader = PdfReader(io.BytesIO(personalized))
        self.assertEqual(len(reader.pages), len(base_reader.pages))
        self.assertGreater(len(reader.pages), 1)

        cover = reader.pages[0].extract_text() or ""
        self.assertIn("MARIA DA SILVA", cover)
        self.assertIn("ESCOLA JOÃO XXIII", cover)
        self.assertIn("9º ANO - TURMA B", cover)
        self.assertIn("Avaliação Municipal 2026", cover)
        self.assertNotIn("MARIA DA SILVA", base_reader.pages[0].extract_text() or "")

        start = individual.answer_sheet_start_page(base)
        self.assertIsNotNone(start)
        self.assertGreater(start, 0)
        for index in range(1, start):
            self.assertEqual(
                reader.pages[index].extract_text(),
                base_reader.pages[index].extract_text(),
            )
        card = "\n".join(reader.pages[i].extract_text() or "" for i in range(start, len(reader.pages)))
        self.assertIn("MARIA DA SILVA", card)
        self.assertIn("Preencha completamente a bolha", card)
        self.assertIn("PÁGINA 1 DE", card)
        self.assertIn("01", card)

        self.assertGreater(len(reader.pages[0].images), len(base_reader.pages[0].images))

    def test_qr_on_cover_decodes_student_and_form(self):
        try:
            from weasyprint import HTML  # noqa: F401
            from pdf2image import convert_from_bytes
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("weasyprint, pdf2image ou opencv não disponíveis")

        base = pdf_service.SocioeconomicQuestionnairePdfService().generate_base_pdf(
            _form(), cover_year=2026
        )
        personalized = individual.personalize_questionnaire_pdf(
            base,
            student_id=STUDENT_ID,
            form_id=FORM_ID,
            student_name="Maria da Silva",
        )
        pages = convert_from_bytes(personalized, dpi=150, first_page=1, last_page=1)
        image = cv2.cvtColor(np.array(pages[0]), cv2.COLOR_RGB2BGR)
        decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
        self.assertTrue(decoded, "QR Code da capa não foi lido")
        payload = json.loads(decoded)
        self.assertEqual(payload["v"], 1)
        self.assertEqual(payload["student_id"], STUDENT_ID[:12])
        self.assertEqual(payload["form_id"], FORM_ID[:12])
