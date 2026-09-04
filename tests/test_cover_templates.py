# -*- coding: utf-8 -*-
"""Testes do template de capa de prova física (sem frontend)."""
import io
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from app.services.cover_templates.constants import A4_HEIGHT_PT, A4_WIDTH_PT
from app.services.cover_templates.coordinates import (
    canonicalize_field_box,
    norm_to_pt,
    pt_to_norm,
)
from app.services.cover_templates.cover_composer import CoverComposer
from app.services.cover_templates.exceptions import (
    CoverTemplateNotFound,
    CoverTemplateValidationError,
)
from app.services.cover_templates.field_catalog import FIELD_KEYS, resolve_field_value
from app.services.cover_templates.file_normalizer import (
    COVER_EMBED_JPEG_QUALITY,
    encode_cover_raster,
    inspect_pdf,
    normalize_upload,
)
from app.services.cover_templates.cover_template_service import CoverTemplateService
from app.services.institutional_test_weasyprint_generator import (
    InstitutionalTestWeasyPrintGenerator,
)


def _a4_pdf_bytes(text: str = "") -> bytes:
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=A4)
    if text:
        canvas.setFont("Helvetica", 12)
        canvas.drawString(72, 720, text)
    canvas.save()
    return buffer.getvalue()


def _a4_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (827, 1169), color=(12, 80, 40))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def _square_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (400, 400), color=(255, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _pdf_image_filters(pdf_bytes: bytes) -> list:
    page = PdfReader(io.BytesIO(pdf_bytes)).pages[0]
    resources = (page.get("/Resources") or {}).get_object()
    xobjects = (resources.get("/XObject") or {})
    if hasattr(xobjects, "get_object"):
        xobjects = xobjects.get_object()
    filters = []
    for name in xobjects:
        obj = xobjects[name].get_object()
        if obj.get("/Subtype") == "/Image":
            filters.append(str(obj.get("/Filter")))
    return filters


class _FakeTemplate:
    def __init__(self):
        self.id = "tpl-1"
        self.test_id = "test-1"
        self.page_width_pt = A4_WIDTH_PT
        self.page_height_pt = A4_HEIGHT_PT
        self.fields = {
            "fields": [
                {
                    "id": "student_name",
                    "key": "aluno.nome",
                    "x_norm": 0.20,
                    "y_norm_from_top": 0.89,
                    "w_norm": 0.74,
                    "h_norm": 0.03,
                    "font_name": "Helvetica-Bold",
                    "font_size_pt": 12,
                    "align": "left",
                    "valign": "middle",
                    "uppercase": True,
                    "overflow": "ellipsis",
                    "max_chars": 55,
                }
            ]
        }


class TestCoverTemplates(unittest.TestCase):
    def test_pdf_valid_stores_mediabox(self):
        original = _a4_pdf_bytes("CAPA ORIGINAL")
        result = normalize_upload("capa.pdf", original)
        self.assertEqual(result["source_kind"], "pdf")
        self.assertEqual(result["page_count"], 1)
        self.assertLess(abs(result["page_width_pt"] - A4_WIDTH_PT), 1)
        self.assertLess(abs(result["page_height_pt"] - A4_HEIGHT_PT), 1)
        self.assertEqual(result["normalized_pdf"], original)
        meta = inspect_pdf(original)
        self.assertEqual(meta["rotation"], 0)

    def test_pdf_multipage_rejected(self):
        writer = PdfWriter()
        writer.add_page(PdfReader(io.BytesIO(_a4_pdf_bytes("p1"))).pages[0])
        writer.add_page(PdfReader(io.BytesIO(_a4_pdf_bytes("p2"))).pages[0])
        out = io.BytesIO()
        writer.write(out)
        with self.assertRaises(CoverTemplateValidationError) as ctx:
            normalize_upload("capa.pdf", out.getvalue())
        self.assertIn("uma página", str(ctx.exception))

    def test_image_valid_creates_normalized_pdf_preserving_original_bytes(self):
        original = _a4_jpeg_bytes()
        result = normalize_upload("capa.jpg", original)
        self.assertEqual(result["source_kind"], "jpeg")
        self.assertEqual(result["mime_type"], "image/jpeg")
        self.assertTrue(result["normalized_pdf"].startswith(b"%PDF"))
        self.assertNotEqual(result["normalized_pdf"], original)
        reader = PdfReader(io.BytesIO(result["normalized_pdf"]))
        self.assertEqual(len(reader.pages), 1)
        box = reader.pages[0].mediabox
        self.assertLess(abs(float(box.width) - A4_WIDTH_PT), 1)
        self.assertLess(abs(float(box.height) - A4_HEIGHT_PT), 1)

    def test_graphic_jpeg_cover_embeds_as_png(self):
        original = _a4_jpeg_bytes()
        result = normalize_upload("capa.jpg", original)
        self.assertEqual(result.get("embed_format"), "PNG")
        self.assertEqual(result.get("source_width_px"), 827)
        self.assertEqual(result.get("source_height_px"), 1169)
        filters = _pdf_image_filters(result["normalized_pdf"])
        self.assertTrue(filters)
        self.assertTrue(all("DCTDecode" not in item for item in filters))

    def test_photo_cover_is_embedded_as_lossless_png(self):
        import numpy as np

        rng = np.random.default_rng(7)
        arr = rng.integers(0, 256, size=(1169, 827, 3), dtype="uint8")
        image = Image.fromarray(arr, "RGB")
        high, fmt = encode_cover_raster(image, "jpeg")
        self.assertEqual(fmt, "PNG")
        self.assertGreaterEqual(COVER_EMBED_JPEG_QUALITY, 90)
        out = Image.open(io.BytesIO(high))
        self.assertEqual(out.size, image.size)
        self.assertEqual(list(out.getdata())[0], list(image.getdata())[0])

    def test_load_print_pdf_uses_original_for_pdf_source(self):
        original = _a4_pdf_bytes("CAPA VETOR")
        svc = CoverTemplateService(minio=MagicMock())
        template = SimpleNamespace(
            source_kind="pdf",
            original_filename="capa.pdf",
            minio_bucket="covers",
            minio_object_name="orig.pdf",
            normalized_object_name="norm.pdf",
        )
        svc.load_original_bytes = lambda _t: (original, "application/pdf")
        self.assertEqual(svc.load_print_pdf_bytes(template), original)

    def test_load_print_pdf_renormalizes_jpeg_original(self):
        original = _a4_jpeg_bytes()
        svc = CoverTemplateService(minio=MagicMock())
        template = SimpleNamespace(
            source_kind="jpeg",
            original_filename="capa.jpg",
            minio_bucket="covers",
            minio_object_name="orig.jpg",
            normalized_object_name="norm.pdf",
        )
        svc.load_original_bytes = lambda _t: (original, "image/jpeg")
        pdf = svc.load_print_pdf_bytes(template)
        self.assertTrue(pdf.startswith(b"%PDF"))
        meta = inspect_pdf(pdf)
        self.assertEqual(meta["page_count"], 1)
        self.assertTrue(all("DCTDecode" not in item for item in _pdf_image_filters(pdf)))

    def test_image_wrong_aspect_rejected(self):
        with self.assertRaises(CoverTemplateValidationError) as ctx:
            normalize_upload("capa.jpg", _square_jpeg_bytes())
        message = str(ctx.exception).lower()
        self.assertTrue("proporção" in message or "a4" in message)

    def test_norm_to_pt_top_left_origin(self):
        x_pt, y_pt, w_pt, h_pt = norm_to_pt(
            0.20, 0.89, 0.74, 0.03, A4_WIDTH_PT, A4_HEIGHT_PT
        )
        self.assertLess(abs(x_pt - 0.20 * A4_WIDTH_PT), 0.01)
        self.assertLess(abs(w_pt - 0.74 * A4_WIDTH_PT), 0.01)
        expected_top = 0.89 * A4_HEIGHT_PT
        expected_y = A4_HEIGHT_PT - expected_top - h_pt
        self.assertLess(abs(y_pt - expected_y), 0.01)
        x_n, y_n, w_n, h_n = pt_to_norm(
            x_pt, y_pt, w_pt, h_pt, A4_WIDTH_PT, A4_HEIGHT_PT
        )
        self.assertLess(abs(x_n - 0.20), 1e-6)
        self.assertLess(abs(y_n - 0.89), 1e-6)
        self.assertLess(abs(w_n - 0.74), 1e-6)
        self.assertLess(abs(h_n - 0.03), 1e-6)

    def test_canonicalize_field_box_from_norm(self):
        box = canonicalize_field_box(
            {
                "x_norm": 0.20,
                "y_norm_from_top": 0.89,
                "w_norm": 0.74,
                "h_norm": 0.03,
            },
            A4_WIDTH_PT,
            A4_HEIGHT_PT,
        )
        self.assertIn("x_pt", box)
        self.assertIn("y_pt", box)
        self.assertLess(box["y_pt"], A4_HEIGHT_PT)

    def test_overlay_merge_produces_valid_pdf(self):
        cover_base = _a4_pdf_bytes("ORIGINAL")
        final_pdf = CoverComposer.compose(
            cover_base,
            _FakeTemplate(),
            student={"name": "Ana Souza"},
            test_data={"title": "Prova"},
            sample=False,
        )
        self.assertTrue(final_pdf.startswith(b"%PDF"))
        reader = PdfReader(io.BytesIO(final_pdf))
        self.assertEqual(len(reader.pages), 1)
        self.assertNotEqual(final_pdf, cover_base)

    def test_field_catalog_does_not_invent_keys(self):
        self.assertIn("aluno.nome", FIELD_KEYS)
        self.assertIn("aluno.matricula", FIELD_KEYS)
        self.assertIn("avaliacao.titulo", FIELD_KEYS)
        self.assertNotIn("professor.nome", FIELD_KEYS)
        self.assertEqual(
            resolve_field_value("aluno.nome", student={"name": "João"}),
            "João",
        )
        self.assertEqual(
            resolve_field_value("avaliacao.titulo", test_data={"title": "Avaliação X"}),
            "Avaliação X",
        )

    def test_isolation_requires_template_of_same_test(self):
        svc = CoverTemplateService(minio=MagicMock())
        with patch(
            "app.services.cover_templates.cover_template_service.Test"
        ) as test_model, patch(
            "app.services.cover_templates.cover_template_service.CoverTemplate"
        ) as cover_model:
            test_model.query.get.return_value = SimpleNamespace(id="test-a")
            cover_model.query.filter_by.return_value.first.return_value = None
            with self.assertRaises(CoverTemplateNotFound):
                svc.get("test-a", "tpl-other-city")

    def test_activate_deactivates_previous_active(self):
        svc = CoverTemplateService(minio=MagicMock())
        template = SimpleNamespace(id="tpl-2", test_id="test-1", status="draft")
        with patch.object(svc, "_require_template", return_value=template), patch(
            "app.services.cover_templates.cover_template_service.CoverTemplate"
        ) as cover_model, patch(
            "app.services.cover_templates.cover_template_service.db"
        ):
            query = cover_model.query.filter.return_value
            result = svc.activate("test-1", "tpl-2")
            query.update.assert_called_once()
            self.assertEqual(result.status, "active")

    def test_fallback_without_active_template(self):
        with patch(
            "app.services.cover_templates.cover_template_service.CoverTemplateService.get_active_for_test",
            return_value=None,
        ):
            generator = InstitutionalTestWeasyPrintGenerator()
            template, pdf = generator._load_active_cover_template({"id": "test-sem-capa"})
            self.assertIsNone(template)
            self.assertIsNone(pdf)


if __name__ == "__main__":
    unittest.main()
